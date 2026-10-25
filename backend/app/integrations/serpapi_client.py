"""Bounded, injectable SerpApi HTTP client. Only public travel search inputs enter here."""
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Lock
from time import monotonic, sleep
from typing import Any

import httpx
from sqlmodel import Session
from app.config import get_settings
from app.db import engine
from app.integrations.cache import cached
from app.integrations.serpapi_normalized import (
    assemble_round_trips, parse_flight_stage1, parse_flight_stage2, parse_hotel_properties,
)


class TravelDataError(Exception):
    """Safe code only: HTTP exceptions can contain the authenticated request URL."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class RequestLimitError(TravelDataError):
    def __init__(self):
        super().__init__("request_limit")


class SerpApiClient:
    def __init__(self, *, transport=None, session_factory=None, settings=None, sleep_fn=sleep):
        self.settings = settings or get_settings()
        self.transport = transport
        self.session_factory = session_factory or (lambda: Session(engine))
        self.sleep = sleep_fn
        self._gate = BoundedSemaphore(max(1, self.settings.serpapi_concurrency))
        self._lock = Lock()
        self.requests = 0
        self.deadline = monotonic() + 270

    def _http(self, params: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.serpapi_key:
            raise TravelDataError("provider_not_configured")
        for attempt in range(self.settings.serpapi_retries + 1):
            retry = False
            with self._gate:
                with self._lock:
                    if self.requests >= self.settings.serpapi_request_limit or monotonic() >= self.deadline:
                        raise RequestLimitError()
                    self.requests += 1
                try:
                    with httpx.Client(transport=self.transport, timeout=min(self.settings.serpapi_timeout, max(0.1, self.deadline - monotonic()))) as client:
                        # Suppress httpx's INFO request logger: the provider requires a query-string key.
                        import logging
                        for logger_name in ("httpx", "httpx2", "httpcore"):
                            logging.getLogger(logger_name).setLevel(logging.WARNING)
                        response = client.get("https://serpapi.com/search.json",
                                              params={**params, "api_key": self.settings.serpapi_key})
                    if response.status_code in (429, 500, 502, 503, 504):
                        retry = True
                    elif response.status_code >= 400:
                        raise TravelDataError("provider_rejected_request")
                    else:
                        data = response.json()
                        if not isinstance(data, dict):
                            raise TravelDataError("malformed_response")
                        metadata = data.get("search_metadata") or {}
                        if not isinstance(metadata, dict) or any(
                            key in data and not isinstance(data[key], list)
                            for key in ("best_flights", "other_flights", "properties", "local_results")):
                            raise TravelDataError("malformed_response")
                        if data.get("error") or metadata.get("status") == "Error":
                            raise TravelDataError("provider_error")
                        return data
                except (httpx.TimeoutException, httpx.TransportError):
                    retry = True
                except (ValueError, TypeError):
                    raise TravelDataError("malformed_response") from None
            if retry and attempt < self.settings.serpapi_retries:
                self.sleep(min(2 ** attempt, 4))
            else:
                raise TravelDataError("provider_unavailable") from None
        raise TravelDataError("provider_unavailable")

    def search(self, params: dict[str, Any]) -> dict[str, Any]:
        ttl = self.settings.lodging_cache_seconds if params["engine"] == "google_hotels" else self.settings.flight_cache_seconds
        with self.session_factory() as session:
            return cached(session, "serpapi", params, lambda: self._http(params), ttl_seconds=ttl,
                          empty_ttl_seconds=self.settings.empty_cache_seconds)

    def round_trips(self, origin: str, destination: str, outbound: str, inbound: str):
        params = {"engine": "google_flights", "departure_id": origin, "arrival_id": destination,
                  "outbound_date": outbound, "return_date": inbound, "type": 1, "adults": 1,
                  "currency": "USD", "hl": "en"}
        options = parse_flight_stage1(self.search(params))
        # Keep one low-price and one short-duration outbound when possible.
        chosen = []
        for key in (lambda f: (f.price_usd is None, f.price_usd or 0, f.signature()),
                    lambda f: (f.total_duration_min is None, f.total_duration_min or 0, f.signature())):
            available = sorted((f for f in options if f.departure_token), key=key)
            if available and all(f.signature() != available[0].signature() for f in chosen):
                chosen.append(available[0])
        for option in sorted(options, key=lambda f: f.signature()):
            if len(chosen) >= 2:
                break
            if option.departure_token and all(option.signature() != f.signature() for f in chosen):
                chosen.append(option)
        trips = []
        for option in chosen:
            choices = parse_flight_stage2(self.search({**params, "departure_token": option.departure_token}),
                                          original_stage1_option=option)
            choices = sorted(choices, key=lambda f: (f.quoted_price_usd is None, f.quoted_price_usd or 0, f.signature()))[:3]
            trips.extend(assemble_round_trips([option], choices))
        return trips

    def properties(self, city: str, checkin: str, checkout: str, adults: int):
        params = {"engine": "google_hotels", "q": city, "check_in_date": checkin, "check_out_date": checkout,
                  "adults": adults, "vacation_rentals": True, "currency": "USD", "hl": "en"}
        kind = getattr(self, 'lodging_kind', 'airbnb')
        if kind != 'airbnb':
            params.pop('vacation_rentals',None)
        if kind == 'hostel':
            params['q'] = city + ' hostels'
        return parse_hotel_properties(self.search(params))

    def collect(self, origins, destination, checkin, checkout, adults):
        """Each task owns its cache session; duplicate origins are fetched only once."""
        failures = []
        def safe(function, *args):
            try:
                return function(*args)
            except TravelDataError as exc:
                failures.append(exc.code)
                return []
        with ThreadPoolExecutor(max_workers=max(1, self.settings.serpapi_concurrency)) as pool:
            pending = {origin: pool.submit(safe, self.round_trips, origin, destination.airports[0], checkin, checkout)
                       for origin in sorted(set(origins))}
            lodging = pool.submit(safe, self.properties, destination.name, checkin, checkout, adults)
            flights = {origin: future.result() for origin, future in pending.items()}
            properties = lodging.result()
        return flights, properties, bool(failures)


# Legacy helpers keep their signatures; their supplied session is not shared with network workers.
def _search(params):
    return SerpApiClient().search(params)


def flights(session, origin, destination, outbound, inbound):
    return _search({"engine": "google_flights", "departure_id": origin, "arrival_id": destination,
                    "outbound_date": outbound, "return_date": inbound, "type": 1, "currency": "USD", "hl": "en"})


def lodging(session, query, check_in, check_out, adults, bedrooms=0):
    return _search({"engine": "google_hotels", "q": query, "check_in_date": check_in, "check_out_date": check_out,
                    "adults": adults, "vacation_rentals": True, "bedrooms": bedrooms, "currency": "USD", "hl": "en"})


def places(session, query, location):
    return _search({"engine": "google_maps", "type": "search", "q": f"{query} in {location}", "hl": "en"})
