"""SerpApi: Google Flights, Google Hotels (incl. vacation rentals) and Google Maps. Every call is cached.
Shortlist 6–8 destinations before pricing: 5 friends × 20 cities would be 100 flight searches per run."""

from typing import Any

import serpapi
from sqlmodel import Session

from app.config import get_settings
from app.integrations.cache import cached


def _search(params: dict[str, Any]) -> dict[str, Any]:
    client = serpapi.Client(api_key=get_settings().serpapi_key, timeout=20)
    return client.search(params).as_dict()


def flights(session: Session, origin: str, destination: str, outbound: str, inbound: str) -> dict[str, Any]:
    """Round trip, e.g. origin="AUS", destination="JFK", dates as YYYY-MM-DD."""
    params = {
        "engine": "google_flights", "departure_id": origin, "arrival_id": destination,
        "outbound_date": outbound, "return_date": inbound, "type": 1, "currency": "USD", "hl": "en",
    }
    return cached(session, "serpapi", params, lambda: _search(params))


def lodging(session: Session, query: str, check_in: str, check_out: str, adults: int, bedrooms: int = 0) -> dict[str, Any]:
    """Vacation rentals fit groups best; drop vacation_rentals for hotels."""
    params = {
        "engine": "google_hotels", "q": query, "check_in_date": check_in, "check_out_date": check_out,
        "adults": adults, "vacation_rentals": True, "bedrooms": bedrooms, "currency": "USD", "hl": "en",
    }
    return cached(session, "serpapi", params, lambda: _search(params))


def places(session: Session, query: str, location: str) -> dict[str, Any]:
    """Restaurants and activities with price levels, e.g. query="vegetarian-friendly restaurants"."""
    params = {"engine": "google_maps", "type": "search", "q": f"{query} in {location}", "hl": "en"}
    return cached(session, "serpapi", params, lambda: _search(params))
