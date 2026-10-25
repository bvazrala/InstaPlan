"""Pydantic models and parsers for SerpApi response schemas verified live (see backend/scripts/serpapi/outputs).

Every model is **source-first** -- it carries a copy of the original JSON object so each field can be traced back to
its provider.  Missing data stays ``None``; nothing is fabricated, inferred or coerced beyond what the provider promises.

Provider limitations that carry into every downstream consumer:

* **Flights** stage-1 returns a *priced option list* (not a booked itinerary). A second call with ``departure_token``
  materialises concrete legs and a ``booking_token``. Prices are per-person totals only.
* **Hotels**: the results array is named ``properties`` (not ``hotels``); ``ads`` must be skipped;
  ``total_rate.after_taxes_fees`` is the trusted full-stay price.
* **Maps**: ``ll``/city-in-query is a search origin, not a geofence.  ``$-$$$$`` levels have no documented dollar map.
* **Events**: the date window is ignored server-side; dates carry no year; ticket_info links only (no prices).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_str(value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None  # type: ignore[return-value]
    return str(value)


def _safe_float(value: Any) -> float | None:
    if value in (None, "", [], {}):
        return None  # type: ignore[return-value]
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value in (None, "", [], {}):
        return None  # type: ignore[return-value]
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Price / completeness enums (for generator use)
# ---------------------------------------------------------------------------

# Legroom values come as "30 in", "76 cm", or a bare number; parse the leading number + optional unit.
_LEGROOM_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(in|inch|cm|mm)?\s*$", flags=re.IGNORECASE)


class PriceStatus(str, Enum):
    QUOTED_WITH_TAXES = "quoted_with_taxes"
    ESTIMATED_BEFORE_TAXES = "estimated_before_taxes"
    UNKNOWN = "unknown"


class FlightStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


# ---------------------------------------------------------------------------
# Flights models -- verified against SERPAPI_AGENT_REFERENCE.md + live runs
# ---------------------------------------------------------------------------

class FlightLeg(BaseModel):
    model_config = ConfigDict(extra="ignore")

    airline: str | None = None
    flight_number: str | None = None  # provider sends "AA 2287" (str) or int; normalised to str
    departure_airport_id: str | None = None
    departure_airport_name: str | None = None
    arrival_airport_id: str | None = None
    arrival_airport_name: str | None = None
    duration_min: int | None = None
    travel_class: str | None = None
    airplane: str | None = None
    scheduled_departure: str | None = None  # provider time string (e.g. "2026-11-05 06:47"), when present
    scheduled_arrival: str | None = None
    legroom_raw: Any = None  # raw value — may be "30 in" or numeric

    def signature(self) -> str:
        """Canonical identity fragment: flight number + airport pair + scheduled times. NOT price."""
        return "|".join(str(x) for x in (
            self.flight_number, self.departure_airport_id, self.arrival_airport_id,
            self.scheduled_departure, self.scheduled_arrival,
        ))

    @property
    def legroom_cm(self) -> float | None:
        """Legroom in cm: '30 in' -> 76.2, '76 cm' -> 76, 30 -> 30 (numeric assumed cm). None when unparseable — never fabricated."""
        if self.legroom_raw is None:
            return None
        if isinstance(self.legroom_raw, (int, float)):
            return float(self.legroom_raw)
        m = _LEGROOM_RE.match(str(self.legroom_raw))
        if not m:
            return None
        value = float(m.group(1))
        unit = (m.group(2) or "").lower()
        if unit in ("in", "inch"):
            return value * 2.54
        if unit == "mm":
            return value / 10.0
        return value  # 'cm' or unit-less -> already cm

    @classmethod
    def from_dict(cls, src: dict[str, Any]) -> FlightLeg:
        dep = src.get("departure_airport", {}) or {}
        arr = src.get("arrival_airport", {}) or {}
        return cls(
            airline=_safe_str(src.get("airline")),
            flight_number=_safe_str(src.get("flight_number")),
            departure_airport_id=_safe_str(dep.get("id")) if isinstance(dep, dict) else None,
            departure_airport_name=_safe_str(dep.get("name")) if isinstance(dep, dict) else None,
            arrival_airport_id=_safe_str(arr.get("id")) if isinstance(arr, dict) else None,
            arrival_airport_name=_safe_str(arr.get("name")) if isinstance(arr, dict) else None,
            duration_min=_safe_int(src.get("duration")),
            travel_class=_safe_str(src.get("travel_class")),
            airplane=_safe_str(src.get("airplane")),
            scheduled_departure=_safe_str(dep.get("time")) if isinstance(dep, dict) else None,
            scheduled_arrival=_safe_str(arr.get("time")) if isinstance(arr, dict) else None,
            legroom_raw=src.get("legroom", src.get("legroom_cm")),
        )


class PriceInsights(BaseModel):
    lowest_price: float | None = None
    typical_price_range: list[float] | None = None
    price_level: str | None = None

    @classmethod
    def from_dict(cls, src: dict[str, Any]) -> PriceInsights:
        if not isinstance(src, dict):
            return cls()
        raw_hist = src.get("price_history") or []
        prices = [p[1] for p in raw_hist if isinstance(p, (list, tuple)) and len(p) == 2]
        return cls(
            lowest_price=_safe_float(src.get("lowest_price")),
            typical_price_range=[float(v) for v in src.get("typical_price_range", []) if v is not None],
            price_level=_safe_str(src.get("price_level")),
        )


class RoundTripFlight(BaseModel):
    """One authoritative, validated complete round-trip: the selected stage-1 outbound + the selected
    stage-2 return.

    Built exclusively via ``build_round_trip`` / ``assemble_round_trips``. The candidate generator
    accepts ONLY this type for a ``COMPLETE`` flight — it never reconstructs itineraries itself.
    """
    model_config = ConfigDict(extra="ignore")

    source: dict[str, Any] = {}
    outbound_flight: list[FlightLeg] = []   # the actual selected stage-1 outbound legs
    return_flight: list[FlightLeg] = []     # the selected stage-2 return legs
    outbound_duration_min: int | None = None
    inbound_duration_min: int | None = None
    total_price_usd: float | None = None     # quoted full fare (provider currency)
    currency: str | None = None
    booking_token: str | None = None
    departure_token: str | None = None       # stage-1 token this was built from
    origin_id: str | None = None
    destination_id: str | None = None
    retrieved_at: datetime | None = None     # provider retrieval time
    complete: bool = False
    incomplete_reasons: list[str] = []

    @property
    def all_flights(self) -> list[FlightLeg]:
        return self.outbound_flight + self.return_flight

    @property
    def leg_count(self) -> int:
        return len(self.all_flights)

    def signature(self) -> str:
        """Canonical identity: outbound + return leg signatures + tokens. NOT price."""
        return (
            "rt|ob=" + ";".join(l.signature() for l in self.outbound_flight)
            + "|ret=" + ";".join(l.signature() for l in self.return_flight)
            + "|bt=" + (self.booking_token or "")
            + "|dt=" + (self.departure_token or "")
        )


class FlightOptionStage1(BaseModel):
    """One flight option from stage-1 (best_flights or other_flights). Represents an *outbound* selection."""
    model_config = ConfigDict(extra="ignore")

    source: dict[str, Any] = {}
    trip_type: str | None = None  # literal "Round trip" / "One-way" / "Multi-city"
    price_usd: float | None = None
    currency: str | None = "USD"
    departure_token: str | None = None
    origin_id: str | None = None
    destination_id: str | None = None
    flights: list[FlightLeg] = []
    total_duration_min: int | None = None
    retrieved_at: datetime | None = None  # provider retrieval time (search_metadata.created_at)

    def signature(self) -> str:
        """Deterministic identity: outbound legs + departure token. NOT price."""
        return "s1|" + ";".join(l.signature() for l in self.flights) + "|tok=" + (self.departure_token or "")

    @classmethod
    def from_dict(cls, src: dict[str, Any], *, retrieved_at: datetime | None = None) -> FlightOptionStage1:
        dep = src.get("departure_airport", {}) or {}
        arr = src.get("arrival_airport", {}) or {}
        return cls(
            source={"engine": "google_flights", "stage": 1},
            trip_type=_safe_str(src.get("type")),
            price_usd=_safe_float(src.get("price")),
            currency=_safe_str(src.get("currency")) or "USD",
            departure_token=_safe_str(src.get("departure_token")),
            origin_id=_safe_str(dep.get("id")) if isinstance(dep, dict) else None,
            destination_id=_safe_str(arr.get("id")) if isinstance(arr, dict) else None,
            flights=[FlightLeg.from_dict(l) for l in (src.get("flights") or []) if isinstance(l, dict)],
            total_duration_min=_safe_int(src.get("total_duration")),
            retrieved_at=retrieved_at,
        )


class FlightOptionComplete(BaseModel):
    """A stage-2 *return* choice for one outbound selection.

    Holds the return legs plus the provider's ``booking_token`` and quoted full fare, bound to the
    stage-1 outbound it belongs to via ``outbound_token``. It is NOT a full itinerary — the outbound
    is owned by ``FlightOptionStage1``. A leg without a ``direction`` field is classified using the
    stage-1 origin/destination context, never silently assumed to be outbound.
    """
    model_config = ConfigDict(extra="ignore")

    source: dict[str, Any] = {}
    outbound_token: str | None = None     # the stage-1 departure_token this return choice belongs to
    origin_id: str | None = None          # stage-1 origin (kept for validation/identity)
    destination_id: str | None = None     # stage-1 destination
    return_flight: list[FlightLeg] = []   # classified return legs only
    booking_token: str | None = None
    quoted_price_usd: float | None = None  # stage-2 quoted full fare
    currency: str | None = None
    total_duration_min: int | None = None
    retrieved_at: datetime | None = None

    def signature(self) -> str:
        """Deterministic identity: return leg signatures + booking token. NOT price."""
        return "s2|" + ";".join(l.signature() for l in self.return_flight) + "|bt=" + (self.booking_token or "")

    @classmethod
    def from_dict(cls, src: dict[str, Any], *, outbound: FlightOptionStage1,
                  retrieved_at: datetime | None = None) -> FlightOptionComplete:
        legs_raw = src.get("flights", []) if isinstance(src.get("flights"), list) else []
        return_flight: list[FlightLeg] = []
        for d in legs_raw:
            if not isinstance(d, dict):
                continue
            direction = str(d.get("direction", "")).lower()
            leg = FlightLeg.from_dict(d)
            if direction == "return":
                return_flight.append(leg)
            elif direction == "outbound":
                continue  # outbound belongs to stage-1; stage-2 is the return-selection stage
            else:
                # No direction: classify by stage-1 context (a leg back to the origin is the return).
                dest_is_origin = bool(outbound.origin_id) and leg.arrival_airport_id == outbound.origin_id
                dep_is_origin = bool(outbound.origin_id) and leg.departure_airport_id == outbound.origin_id
                if dest_is_origin and not dep_is_origin:
                    return_flight.append(leg)

        return cls(
            source={"engine": "google_flights", "stage": 2},
            outbound_token=outbound.departure_token,
            origin_id=outbound.origin_id,
            destination_id=outbound.destination_id,
            return_flight=return_flight,
            booking_token=_safe_str(src.get("booking_token")),
            quoted_price_usd=_safe_float(src.get("price")),
            currency=_safe_str(src.get("currency")) or outbound.currency,
            total_duration_min=_safe_int(src.get("total_duration")),
            retrieved_at=retrieved_at,
        )


def build_round_trip(outbound: FlightOptionStage1, choice: FlightOptionComplete) -> RoundTripFlight:
    """Strict reconstruction of a complete round-trip from a stage-1 outbound and a stage-2 return choice.

    The association is already established by ``departure_token`` (no price- or first-option matching).
    Missing legs, a missing booking token, or a route discontinuity keep ``complete=False`` and record why.
    """
    reasons: list[str] = []
    if choice.outbound_token and outbound.departure_token and choice.outbound_token != outbound.departure_token:
        reasons.append(f"token_mismatch:{choice.outbound_token}!={outbound.departure_token}")
    if not outbound.flights:
        reasons.append("no_outbound_legs")
    if not choice.return_flight:
        reasons.append("no_return_legs")
    if not choice.booking_token:
        reasons.append("no_booking_token")

    # Route continuity: last outbound arrival must equal first return departure.
    if outbound.flights and choice.return_flight:
        last_out_arrival = outbound.flights[-1].arrival_airport_id
        first_ret_departure = choice.return_flight[0].departure_airport_id
        if last_out_arrival and first_ret_departure and last_out_arrival != first_ret_departure:
            reasons.append(f"route_mismatch:{last_out_arrival}!={first_ret_departure}")

    return RoundTripFlight(
        source={"engine": "google_flights", "stage": 1, "aggregated_from_stage2": True,
                "outbound_array": outbound.source.get("array_name"),
                "return_array": choice.source.get("array_name")},
        outbound_flight=list(outbound.flights),
        return_flight=list(choice.return_flight),
        outbound_duration_min=outbound.total_duration_min,
        inbound_duration_min=choice.return_flight[0].duration_min if choice.return_flight else None,
        total_price_usd=choice.quoted_price_usd if choice.quoted_price_usd is not None else outbound.price_usd,
        currency=choice.currency or outbound.currency or "USD",
        booking_token=choice.booking_token,
        departure_token=outbound.departure_token,
        origin_id=outbound.origin_id,
        destination_id=outbound.destination_id,
        retrieved_at=choice.retrieved_at or outbound.retrieved_at,
        complete=not reasons,
        incomplete_reasons=reasons,
    )


def assemble_round_trips(stage1_options: list[FlightOptionStage1],
                         stage2_choices: list[FlightOptionComplete]) -> list[RoundTripFlight]:
    """Pair stage-1 outbound selections with stage-2 return choices by ``departure_token`` (never by price/first).

    A return choice with no matching stage-1 outbound is left out (kept diagnostic) rather than force-matched.
    """
    out: list[RoundTripFlight] = []
    for choice in stage2_choices:
        for option in stage1_options:
            if option.departure_token and option.departure_token == choice.outbound_token:
                out.append(build_round_trip(option, choice))
    return out


# ---------------------------------------------------------------------------
# Hotels / vacation-rental models (google_hotels engine)
# ---------------------------------------------------------------------------

class PriceDict(BaseModel):
    """A SerpApi price dict: before_taxes_fees / after_taxes_fees / display_price + extracted variants."""
    before_taxes_fees: float | None = None
    after_taxes_fees: float | None = None
    display_price: float | None = None
    extracted_before_taxes_fees: float | None = None
    extracted_after_taxes_fees: float | None = None

    @classmethod
    def from_dict(cls, src: Any) -> PriceDict | None:
        if not isinstance(src, dict):
            return None
        return cls(
            before_taxes_fees=_safe_float(src.get("before_taxes_fees")),
            after_taxes_fees=_safe_float(src.get("after_taxes_fees")),
            display_price=_safe_float(src.get("display_price")),
            extracted_before_taxes_fees=_safe_float(src.get("extracted_before_taxes_fees")),
            extracted_after_taxes_fees=_safe_float(src.get("extracted_after_taxes_fees")),
        )


class Property(BaseModel):
    """A vacation rental or hotel row from google_hotels."""
    model_config = ConfigDict(extra="ignore")

    source: dict[str, Any] = {}
    name: str | None = None
    accommodation_type: str | None = None
    rate_per_night: PriceDict | None = None
    total_rate: PriceDict | None = None
    currency: str | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    overall_rating: float | None = None
    review_count: int | None = None  # NEVER used as occupancy — confirmed, no capacity field in SerpApi schema
    property_token: str | None = None
    amenities: list[str] = []
    booking_link: str | None = None
    max_occupancy: int | None = None  # from provider when present; otherwise always None (verified=None)
    retrieved_at: datetime | None = None  # provider retrieval time (search_metadata.created_at)

    @property
    def has_total_price(self) -> bool:
        """True when total_rate.after_taxes_fees or extracted_ variant is populated."""
        if self.total_rate is None:
            return False
        return bool(self.total_rate.extracted_after_taxes_fees or self.total_rate.after_taxes_fees)

    @property
    def has_per_night_price(self) -> bool:
        """True when rate_per_night has a recognizable price field."""
        if self.rate_per_night is None:
            return False
        return bool(self.rate_per_night.extracted_before_taxes_fees or self.rate_per_night.display_price)

    @computed_field
    @property
    def location_label(self) -> str | None:
        # FIX: ensure BOTH coordinates are present before formatting (P1.12 safety)
        if self.name and (self.gps_latitude is not None) and (self.gps_longitude is not None):  # type: ignore[operator]
            return f"{self.name} ({self.gps_latitude:.4f}, {self.gps_longitude:.4f})"
        return self.name

    @classmethod
    def from_dict(cls, src: dict[str, Any], engine: str = "google_hotels",
                  *, retrieved_at: datetime | None = None) -> Property:
        gps = src.get("gps_coordinates", {}) or {}
        return cls(
            source={"engine": engine, "array_name": "properties"},
            name=_safe_str(src.get("name")),
            accommodation_type=_safe_str(src.get("accommodation_type") or src.get("type")),
            rate_per_night=PriceDict.from_dict(src.get("rate_per_night")),
            total_rate=PriceDict.from_dict(src.get("total_rate")),
            currency=_safe_str(src.get("currency")),
            gps_latitude=_safe_float(gps.get("latitude")) if isinstance(gps, dict) else None,
            gps_longitude=_safe_float(gps.get("longitude")) if isinstance(gps, dict) else None,
            overall_rating=_safe_float(src.get("overall_rating")),
            review_count=_safe_int(src.get("reviews")),
            property_token=_safe_str(src.get("property_token")),
            amenities=src.get("amenities") if isinstance(src.get("amenities"), list) else [],
            booking_link=_safe_str(src.get("link") or src.get("booking_link")),
            max_occupancy=_safe_int(src.get("max_occupancy")),  # only from explicit provider field; None if absent
            retrieved_at=retrieved_at,
        )


# ---------------------------------------------------------------------------
# Google Maps / places model (google_maps engine)
# ---------------------------------------------------------------------------

class Place(BaseModel):
    """A place row from google_maps local_results."""
    model_config = ConfigDict(extra="ignore")

    source: dict[str, Any] = {}
    title: str | None = None
    category: str | None = None  # mapped from "type"
    types: list[str] = []
    rating: float | None = None
    review_count: int | None = None
    price_level: str | None = None  # "$", "$$", etc. -- NOT converted to dollars
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    place_id: str | None = None
    data_id: str | None = None
    data_cid: str | None = None
    phone: str | None = None
    website_url: str | None = None
    open_state: str | None = None
    operating_hours_raw: Any = None

    @classmethod
    def from_dict(cls, src: dict[str, Any], engine: str = "google_maps") -> Place:
        gps = src.get("gps_coordinates", {}) or {}
        types = [_safe_str(t) for t in (src.get("types") or []) if isinstance(t, (str, int, float))]
        op_hours = src.get("operating_hours") or {}
        if isinstance(op_hours, list):
            hours = op_hours  # type: ignore[assignment]
        else:
            hours = {k: v for k, v in op_hours.items() if isinstance(k, str) and isinstance(v, str)}
        return cls(
            source={"engine": engine, "array_name": "local_results"},
            title=_safe_str(src.get("title")),
            category=_safe_str(src.get("type")),
            types=[t for t in types if t],
            rating=_safe_float(src.get("rating")),
            review_count=_safe_int(src.get("reviews")),
            price_level=_safe_str(src.get("price")),
            address=_safe_str(src.get("address")),
            latitude=_safe_float(gps.get("latitude")) if isinstance(gps, dict) else None,
            longitude=_safe_float(gps.get("longitude")) if isinstance(gps, dict) else None,
            place_id=_safe_str(src.get("place_id")),
            data_id=_safe_str(src.get("data_id")),
            data_cid=_safe_str(src.get("data_cid")),
            phone=_safe_str(src.get("phone")),
            website_url=_safe_str(src.get("website")),
            open_state=_safe_str(src.get("open_state")),
            operating_hours_raw=hours,
        )


# ---------------------------------------------------------------------------
# Events model (google_events engine)
# ---------------------------------------------------------------------------

class Event(BaseModel):
    """A SerpApi google_events row. Dates carry no year; the date window is ignored server-side."""
    model_config = ConfigDict(extra="ignore")

    source: dict[str, Any] = {}
    title: str | None = None
    date_start_month_day: str | None = None  # e.g. "Nov 5"
    date_full_display: str | None = None      # e.g. "Nov 5, 6:00 PM"
    venue_name: str | None = None
    venue_link_url: str | None = None
    address_list: list[str] = []
    ticket_info: list[dict[str, str | None]] = []
    event_token: str | None = None

    @property
    def month_day_parts(self) -> tuple[str | None, str | None]:
        """Split 'Nov 5' into ('Nov', '5') for client-side date matching."""
        if not self.date_start_month_day:
            return None, None
        parts = self.date_start_month_day.split(" ")
        return (parts[0] if len(parts) >= 1 else None, parts[1] if len(parts) >= 2 else None)

    @classmethod
    def from_dict(cls, src: dict[str, Any], engine: str = "google_events") -> Event:
        date_obj = src.get("date", {}) or {}
        v = src.get("venue", {}) or {}
        ticket_raw = src.get("ticket_info", [])
        tickets: list[dict[str, str | None]] = []
        if isinstance(ticket_raw, list):
            for t in ticket_raw:
                if isinstance(t, dict):
                    tickets.append({
                        "source": _safe_str(t.get("source")) or "",
                        "link_url": _safe_str(t.get("link")),
                        "link_type": _safe_str(t.get("link_type")),
                    })
        return cls(
            source={"engine": engine, "array_name": "events_results"},
            title=_safe_str(src.get("title")),
            date_start_month_day=_safe_str(date_obj.get("start_date") or src.get("_date_raw", "")),
            date_full_display=_safe_str(date_obj.get("when")),
            venue_name=_safe_str(v.get("name")),
            venue_link_url=_safe_str(v.get("link")),
            address_list=src.get("address") if isinstance(src.get("address"), list) else [],
            ticket_info=tickets,
            event_token=_safe_str(src.get("event_token")),
        )


# ---------------------------------------------------------------------------
# Google Search model (google engine)
# ---------------------------------------------------------------------------

class SearchResult(BaseModel):
    """An organic search result row."""
    model_config = ConfigDict(extra="ignore")

    source: dict[str, Any] = {}  # engine + array_name
    position: int | None = None
    title: str | None = None
    url: str | None = None
    snippet: str | None = None
    date: str | None = None

    @classmethod
    def from_dict(cls, src: dict[str, Any], engine: str = "google") -> SearchResult:
        return cls(
            source={"engine": engine, "array_name": "organic_results"},
            position=_safe_int(src.get("position")),
            title=_safe_str(src.get("title")),
            url=_safe_str(src.get("link")),
            snippet=_safe_str(src.get("snippet")),
            date=_safe_str(src.get("date")),
        )


class AiOverview(BaseModel):
    """The ai_overview structured section from google search."""
    snippet: str | None = None
    source_title: str | None = None
    source_url: str | None = None

    @classmethod
    def from_dict(cls, src: dict[str, Any]) -> AiOverview:
        src_meta = src.get("source", {}) or {} if isinstance(src, dict) else {}
        return cls(
            snippet=_safe_str(src.get("snippet")) if isinstance(src, dict) else None,
            source_title=_safe_str(src_meta.get("title")),
            source_url=_safe_str(src_meta.get("link")),
        )


# ---------------------------------------------------------------------------
# Batch parsers (work on a raw JSON dict from SerpApi)
# ---------------------------------------------------------------------------

def _parse_created_at(raw: dict[str, Any]) -> datetime | None:
    """Provider retrieval time from search_metadata.created_at (ISO-8601; trailing Z tolerated). """
    meta = raw.get("search_metadata")
    ts = meta.get("created_at") if isinstance(meta, dict) else None
    if not isinstance(ts, str) or not ts.strip():
        return None
    value = ts.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def parse_flight_stage1(raw: dict[str, Any]) -> list[FlightOptionStage1]:
    """Extract all flight options from stage-1 (best_flights + other_flights). Each is an *outbound* selection."""
    retrieved_at = _parse_created_at(raw)
    defaults = raw.get("search_parameters") or {}
    options: list[FlightOptionStage1] = []
    for key in ("best_flights", "other_flights"):
        arr = raw.get(key) or []
        if not isinstance(arr, list):
            continue
        for item in arr:
            if isinstance(item, dict):
                opt = FlightOptionStage1.from_dict(item, retrieved_at=retrieved_at)
                opt.source["array_name"] = key  # type: ignore[typeddict-item]
                if opt.origin_id is None:
                    opt.origin_id = _safe_str(defaults.get("departure_id"))
                if opt.destination_id is None:
                    opt.destination_id = _safe_str(defaults.get("arrival_id"))
                if opt.currency is None:
                    opt.currency = _safe_str(defaults.get("currency")) or "USD"
                options.append(opt)
    return options


def parse_flight_stage2(raw: dict[str, Any], *, original_stage1_option: FlightOptionStage1 | None = None
                        ) -> list[FlightOptionComplete]:
    """Extract stage-2 *return* choices. Each is bound to the stage-1 outbound it belongs to via its departure_token.

    ``original_stage1_option`` supplies the context used to classify return legs; when omitted, the
    token/route come from ``search_parameters`` (the stage-2 call is made with a specific departure_token).
    """
    retrieved_at = _parse_created_at(raw)
    defaults = raw.get("search_parameters") or {}
    outbound = original_stage1_option
    if outbound is None:
        outbound = FlightOptionStage1(
            source={"engine": "google_flights", "stage": 1, "synthetic": True},
            departure_token=_safe_str(defaults.get("departure_token")),
            origin_id=_safe_str(defaults.get("departure_id")),
            destination_id=_safe_str(defaults.get("arrival_id")),
            currency=_safe_str(defaults.get("currency")) or "USD",
            retrieved_at=retrieved_at,
        )
    results: list[FlightOptionComplete] = []
    for key in ("other_flights", "best_flights"):
        arr = raw.get(key) or []
        if not isinstance(arr, list):
            continue
        for item in arr:
            if isinstance(item, dict):
                comp = FlightOptionComplete.from_dict(item, outbound=outbound, retrieved_at=retrieved_at)
                comp.source["array_name"] = key  # type: ignore[typeddict-item]
                results.append(comp)
    return results


def parse_hotel_properties(raw: dict[str, Any]) -> list[Property]:
    """Extract only the *properties* array (skip ``ads`` which may also contain price dicts)."""
    retrieved_at = _parse_created_at(raw)
    props: list[Property] = []
    for prop_row in (raw.get("properties") or []):
        if isinstance(prop_row, dict):
            p = Property.from_dict(prop_row, engine="google_hotels", retrieved_at=retrieved_at)
            props.append(p)
    return props


def parse_maps_places(raw: dict[str, Any]) -> list[Place]:
    """Extract local_results from a google_maps response."""
    places: list[Place] = []
    for row in (raw.get("local_results") or []):
        if isinstance(row, dict):
            p = Place.from_dict(row, engine="google_maps")
            places.append(p)
    return places


def parse_events(raw: dict[str, Any]) -> list[Event]:
    """Extract events_rows from a google_events response."""
    evts: list[Event] = []
    for row in (raw.get("events_results") or []):
        if isinstance(row, dict):
            e = Event.from_dict(row, engine="google_events")
            evts.append(e)
    return evts


def parse_search(raw: dict[str, Any]) -> tuple[list[SearchResult], AiOverview | None]:
    """Extract organic_results and optional ai_overview from a google search response."""
    results: list[SearchResult] = []
    for row in (raw.get("organic_results") or []):
        if isinstance(row, dict):
            results.append(SearchResult.from_dict(row, engine="google"))
    overview_source = raw.get("ai_overview", {})
    ai: AiOverview | None = AiOverview.from_dict(overview_source) if isinstance(overview_source, dict) else None
    return results, ai
