"""Standalone trip-candidate builder for SerpApi-parsed data.

Given a flight selection — either a validated ``RoundTripFlight`` (built via ``build_round_trip``
from a stage-1 outbound + stage-2 return choice) or a stage-1 outbound-only option (incomplete) —
paired with hotel/rental ``Property`` rows, produce validated ``TripCandidate`` objects with:

* an **identity** derived from flight numbers, airport pairs, scheduled times and booking/departure
  tokens (never price, so three same-price returns keep three distinct ids);
* an **independent** flight completeness status and lodging price coverage;
* **Decimal** arithmetic for all computed sums; cross-currency aggregation is refused;
* a **structured** lodging price object (amount / status / currency / tax_inclusive) so nightly-rate
  estimates can never masquerade as tax-inclusive full-stay quotes;
* a **provider** ``priced_at`` (retrieval time), never the candidate-generation time;
* **segregated ineligible** candidates (incomplete flights, unknown price, unverified capacity) placed
  after all eligible ones, for diagnostics/UI — they never outrank a complete flight with a detailed
  lodging quote.

Pure module: **no** FastAPI, no database, no SerpApi HTTP calls.
"""

from __future__ import annotations

import hashlib
import json as _json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any

from app.integrations.serpapi_normalized import (
    FlightOptionStage1,
    FlightOptionComplete,
    RoundTripFlight,
    Property,
    FlightStatus,
    assemble_round_trips,
)


# ---------------------------------------------------------------------------
# Decimal helpers (all monetary math uses Decimal to avoid float drift)
# ---------------------------------------------------------------------------

CENTS = Decimal("0.01")


def _to_decimal(value: Any) -> Decimal | None:
    """Convert a provider number (float / int / str) to Decimal without float error. None -> None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ValueError, ArithmeticError):
        return None


def _round2(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Enums + structured price object
# ---------------------------------------------------------------------------

class LodgingCompliance(str, Enum):
    """What price coverage exists for lodging. Never conflated with flight status."""
    QUOTED_WITH_TAXES = "quoted_with_taxes"      # total_rate.after_taxes_fees verified (full stay)
    ESTIMATED = "estimated_before_taxes"         # rate_per_night x nights (no taxes/fees)
    MISSING = "missing"                          # No price field at all
    UNKNOWN = "unknown"

    @property
    def has_cost(self) -> bool:
        return self in (LodgingCompliance.QUOTED_WITH_TAXES, LodgingCompliance.ESTIMATED)


@dataclass(frozen=True)
class LodgingPrice:
    """Structured lodging price: amount + coverage status + currency + tax inclusivity.

    Distinguishes quoted (taxed) and estimated (nightly-derived) in **both** name and status.
    """
    amount: Decimal | None            # present ONLY for QUOTED_WITH_TAXES / ESTIMATED
    status: LodgingCompliance
    currency: str
    tax_inclusive: bool               # True only for QUOTED_WITH_TAXES

    @property
    def has_cost(self) -> bool:
        return self.amount is not None and self.status.has_cost


# ---------------------------------------------------------------------------
# Candidate (immutable value object)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TripCandidate:
    """A single lodging option paired with a single flight selection."""
    # Identity
    id: str
    # Metadata
    title: str
    place: str
    dates: str           # "YYYY-MM-DD..YYYY-MM-DD"
    nights: int
    lodging_name: str
    # Lodging — structured price object + explicit status. Never conflated with flight status.
    lodging_price: LodgingPrice
    lodging_per_person: Decimal | None
    occupancy_adults: int | None            # NEVER derived from review_count — only verified provider data
    capacity_verified: bool                 # single source of truth (derived below)
    # Flight — explicit status and per-person USD.
    flight_price_usd: Decimal | None
    flight_status: FlightStatus
    booking_token: str | None               # traceability
    # Aggregate (per-person) — populated only when a single shared currency AND both inputs are present.
    total_per_person: Decimal | None
    currency: str
    # Warnings — each a distinct concern; never combined into a fake "completeness" score.
    warnings: tuple[str, ...]
    # Traceability
    lodging_source: dict
    flight_source: dict
    priced_at: datetime | None              # provider retrieval time, NOT generation time

    @property
    def capacity_unverified(self) -> bool:
        """Derived from ``capacity_verified`` — never stored independently (avoids contradiction)."""
        return not self.capacity_verified

    @classmethod
    def from_combination(
        cls,
        flight: FlightOptionStage1 | RoundTripFlight,
        property_: Property,
        *,
        checkin: str,
        checkout: str,
        adults: int,
        destination_city: str = "New York City",
    ) -> TripCandidate:
        """Derive a ``TripCandidate`` from one flight selection + one lodging row.

        ``flight`` is either a validated ``RoundTripFlight`` (COMPLETE / PARTIAL / MISSING via
        ``flight.complete``) or a ``FlightOptionStage1`` (outbound-only, always PARTIAL or MISSING).
        """
        nights = _validate_nights(checkin, checkout)  # raises InvalidDatesError (a ValueError)
        dates_str = f"{checkin}..{checkout}"
        warnings: list[str] = []

        # -- flight -----------------------------------------------------------------------------
        if isinstance(flight, RoundTripFlight):
            if flight.complete:
                flight_status = FlightStatus.COMPLETE
            elif flight.all_flights:
                flight_status = FlightStatus.PARTIAL
                warnings.extend(f"incomplete:{reason}" for reason in flight.incomplete_reasons)
            else:
                flight_status = FlightStatus.MISSING
                warnings.append("flight_missing")
            flight_price = _to_decimal(flight.total_price_usd)
            booking_token = flight.booking_token
            flight_currency = (flight.currency or "USD").upper()
            retrieved_at = flight.retrieved_at
        else:  # FlightOptionStage1: an incomplete outbound selection — NEVER complete
            flight_status = FlightStatus.PARTIAL if flight.flights else FlightStatus.MISSING
            if flight_status == FlightStatus.MISSING:
                warnings.append("flight_missing")
            else:
                warnings.append("flight_only_outbound_no_return")
            flight_price = _to_decimal(flight.price_usd)
            booking_token = None
            flight_currency = (flight.currency or "USD").upper()
            retrieved_at = flight.retrieved_at

        # -- lodging price (structured; quoted vs estimate never conflated) -----------------------
        lodging_currency = (property_.currency or flight_currency or "USD").upper()
        amount: Decimal | None = None
        price_status: LodgingCompliance = LodgingCompliance.UNKNOWN
        tax_inclusive = False

        if property_.has_total_price and property_.total_rate is not None:
            raw = property_.total_rate
            value = _to_decimal(raw.extracted_after_taxes_fees)
            if value is None:
                value = _to_decimal(raw.after_taxes_fees)
            if value is not None:
                amount = value
                price_status = LodgingCompliance.QUOTED_WITH_TAXES
                tax_inclusive = True

        if price_status is LodgingCompliance.UNKNOWN and property_.has_per_night_price \
                and property_.rate_per_night is not None:
            raw = property_.rate_per_night
            nightly = _to_decimal(raw.extracted_before_taxes_fees)
            if nightly is None:
                nightly = _to_decimal(raw.display_price)
            if nightly is not None and adults > 0:
                amount = _round2(nightly * Decimal(nights))
                price_status = LodgingCompliance.ESTIMATED
                tax_inclusive = False
                warnings.append("lodging_estimate_from_nightly_rate")

        if price_status is LodgingCompliance.UNKNOWN:
            price_status = LodgingCompliance.MISSING
            warnings.append("lodging_no_price_coverage")

        # -- auxiliary lodging signals (each its own concern, never merged) ------------------------
        if not property_.amenities:
            warnings.append("lodging_no_amenities_listed")
        if property_.review_count is None or property_.overall_rating is None:
            warnings.append("lodging_no_reviews_or_rating")
        capacity_verified = property_.max_occupancy is not None
        if not capacity_verified:
            warnings.append("lodging_capacity_not_verified")
        occupancy_adults = property_.max_occupancy  # NEVER derived from review_count

        # -- aggregate (currency-aware: cross-currency is NEVER summed) -----------------------------
        lodging_per_person: Decimal | None = None
        total_per_person: Decimal | None = None
        currency_matches = (lodging_currency == flight_currency)
        if not currency_matches:
            warnings.append(f"currency_mismatch:{lodging_currency}!={flight_currency}")
        else:
            if amount is not None and adults > 0:
                lodging_per_person = _round2(amount / Decimal(adults))
            if flight_price is not None and lodging_per_person is not None:
                total_per_person = _round2(flight_price + lodging_per_person)

        lodging_price = LodgingPrice(
            amount=amount,
            status=price_status,
            currency=lodging_currency,
            tax_inclusive=tax_inclusive,
        )

        # -- identity + provenance -----------------------------------------------------------------
        candidate_id = make_candidate_id(flight, property_, (checkin, checkout))
        title = f"{destination_city} — {property_.name or 'Unknown property'}"

        return cls(
            id=candidate_id,
            title=title,
            place=destination_city,
            dates=dates_str,
            nights=nights,
            lodging_name=property_.name or "Unknown property",
            lodging_price=lodging_price,
            lodging_per_person=lodging_per_person,
            occupancy_adults=occupancy_adults,
            capacity_verified=capacity_verified,
            flight_price_usd=flight_price,
            flight_status=flight_status,
            booking_token=booking_token,
            total_per_person=total_per_person,
            currency=flight_currency,
            warnings=tuple(warnings),
            lodging_source=dict(getattr(property_, "source", {}) or {}),
            flight_source=dict(getattr(flight, "source", {}) or {}),
            priced_at=retrieved_at if retrieved_at is not None else property_.retrieved_at,
        )


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

def make_candidate_id(
    flight: FlightOptionStage1 | RoundTripFlight,
    property_: Property,
    dates: tuple[str, str],
) -> str:
    """Deterministic unique candidate id from itinerary × lodging × dates.

    Built from flight numbers, airport pairs, scheduled times and booking/departure tokens — NOT price —
    so three same-price return itineraries still produce three distinct ids, while a genuine duplicate
    (identical legs + tokens + property + dates) still compresses to one.
    """
    signature = flight.signature()
    prop = property_.property_token or hashlib.sha256((property_.name or "").encode()).hexdigest()[:10]
    canonical = _json.dumps(
        {"it": signature, "prop": prop, "dates": [str(x) for x in dates]},
        sort_keys=True,
        separators=(",", ":"),
    )
    return "tc-" + hashlib.sha256(canonical.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Date validation
# ---------------------------------------------------------------------------

class InvalidDatesError(ValueError):
    """Raised when checkin/checkout cannot be parsed or do not yield a positive night count."""


def _validate_nights(checkin: str, checkout: str) -> int:
    """Parse dates and validate — NEVER silently default. Raises InvalidDatesError on failure."""
    from datetime import date as _date

    try:
        d1 = datetime.strptime(checkin, "%Y-%m-%d").date()
        d2 = datetime.strptime(checkout, "%Y-%m-%d").date()
    except (ValueError, TypeError) as exc:
        raise InvalidDatesError(f"Cannot parse dates: checkin='{checkin}' checkout='{checkout}': {exc}") from None
    nights = (d2 - d1).days
    if nights <= 0:
        raise InvalidDatesError(f"Non-positive nights={nights} for checkin={checkin} checkout={checkout}")
    return nights


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_all_candidates(
    flights_stage1: list[FlightOptionStage1] | None = None,
    hotels_properties: list[Property] | None = None,
    *,
    round_trips: list[RoundTripFlight] | None = None,
    stage2_return_choices: list[FlightOptionComplete] | None = None,
    checkin: str = "2026-11-05",
    checkout: str = "2026-11-09",
    adults: int = 4,
    destination_city: str = "New York City",
) -> list[TripCandidate]:
    """Pair flight selections with hotel properties; return eligible candidates first.

    A candidate is *eligible* — a valid trip recommendation — only when the flight is COMPLETE and
    lodging has a cost. Ineligible candidates (incomplete flights, missing price, unverified
    capacity, ...) are returned AFTER all eligible ones, for diagnostic/UI purposes. They are never
    promoted by a more detailed lodging quote.
    """
    flights_stage1 = list(flights_stage1 or [])
    hotels = list(hotels_properties or [])
    rts = list(round_trips or [])
    choices = list(stage2_return_choices or [])
    if choices and flights_stage1:
        rts = rts + assemble_round_trips(flights_stage1, choices)

    _validate_nights(checkin, checkout)  # raises InvalidDatesError (a ValueError) once, up front

    results: list[TripCandidate] = []
    seen: set[str] = set()
    for flight in list(rts) + list(flights_stage1):
        for prop in hotels:
            tc = TripCandidate.from_combination(
                flight, prop,
                checkin=checkin, checkout=checkout,
                adults=adults, destination_city=destination_city,
            )
            if tc.id in seen:
                continue
            seen.add(tc.id)
            results.append(tc)

    def eligible(tc: TripCandidate) -> bool:
        return tc.flight_status == FlightStatus.COMPLETE and tc.lodging_price.has_cost

    def rank_key(tc: TripCandidate) -> tuple[int, Decimal]:
        price_rank = 0 if tc.lodging_price.status == LodgingCompliance.QUOTED_WITH_TAXES else 1
        cost = tc.total_per_person if tc.total_per_person is not None else Decimal("Infinity")
        return (price_rank, cost)

    eligible_list = sorted((tc for tc in results if eligible(tc)), key=rank_key)
    rest = [tc for tc in results if not eligible(tc)]
    return eligible_list + rest


__all__ = [
    "LodgingCompliance",
    "LodgingPrice",
    "TripCandidate",
    "make_candidate_id",
    "build_all_candidates",
    "InvalidDatesError",
]
