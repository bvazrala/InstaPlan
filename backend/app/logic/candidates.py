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
from dataclasses import dataclass, replace
from collections.abc import Mapping, Sequence
from heapq import nsmallest
from itertools import islice
from datetime import UTC, datetime
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
    try:
        amount = Decimal(str(value))
        return amount if amount.is_finite() and amount >= 0 else None
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


class FeasibilityStatus(str, Enum):
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class Participant:
    """Group-visible identity and airport; no private preferences or budgets."""
    user_id: str
    origin_airport: str

    def __post_init__(self) -> None:
        if not self.user_id.strip() or not self.origin_airport.strip():
            raise ValueError("Participant user_id and origin_airport are required")
        object.__setattr__(self, "origin_airport", self.origin_airport.strip().upper())


@dataclass(frozen=True)
class ParticipantTravel:
    user_id: str
    origin_airport: str
    flight: RoundTripFlight | None  # retains source, tokens, legs and provider retrieval time
    flight_cost: Decimal | None
    currency: str | None
    lodging_allocation: Decimal | None
    estimated_subtotal: Decimal | None  # flights + lodging only; never food/activities
    travel_duration_min: int | None  # outbound + inbound elapsed duration, including layovers
    flight_status: FlightStatus


# ---------------------------------------------------------------------------
# Candidate (immutable value object)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TripCandidate:
    """Group trip, or a legacy single-flight example when participants is empty."""
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
    currency: str | None
    # Warnings — each a distinct concern; never combined into a fake "completeness" score.
    warnings: tuple[str, ...]
    # Traceability
    lodging_source: dict
    flight_source: dict
    priced_at: datetime | None              # provider retrieval time, NOT generation time

    # Group generation never fills the legacy single-flight/average cost fields above.
    participants: tuple[ParticipantTravel, ...] = ()
    group_total: Decimal | None = None
    max_travel_duration_min: int | None = None
    feasibility: FeasibilityStatus = FeasibilityStatus.UNVERIFIED
    feasibility_reasons: tuple[str, ...] = ()
    complete: bool = False  # every flight complete, all prices quoted, common known currency
    lodging_priced_at: datetime | None = None
    lodging_amenities: tuple[str, ...] = ()
    listing_url: str | None = None

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
            lodging_priced_at=property_.retrieved_at,
            lodging_amenities=tuple(property_.amenities),
            listing_url=property_.booking_link,
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


# Group generation uses identity ordering and evidence quality only. Preference scoring,
# price/time strategy ranking and private budget fairness belong to subsequent stages.

def _currency(value: str | None) -> str | None:
    return value.strip().upper() if value and value.strip() else None


def _flight_evidence(participant: Participant, flight: RoundTripFlight | None,
                     checkin: str, checkout: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    hard: list[str] = []
    unknown: list[str] = []
    uid = participant.user_id
    if flight is None:
        return (), (f"flight_missing:{uid}",)
    if not flight.complete or not flight.outbound_flight or not flight.return_flight or not flight.booking_token:
        unknown.append(f"flight_incomplete:{uid}")
        unknown.extend(f"flight_incomplete:{uid}:{reason}" for reason in flight.incomplete_reasons)
    if _to_decimal(flight.total_price_usd) is None:
        unknown.append(f"flight_price_missing:{uid}")
    if _currency(flight.currency) is None:
        unknown.append(f"flight_currency_unknown:{uid}")
    if _travel_duration(flight) is None:
        unknown.append(f"travel_duration_unknown:{uid}")
    if flight.origin_id and flight.origin_id.upper() != participant.origin_airport:
        hard.append(f"origin_mismatch:{uid}")
    outbound, inbound = flight.outbound_flight, flight.return_flight
    if outbound and inbound:
        for observed in (outbound[0].departure_airport_id, inbound[-1].arrival_airport_id):
            if observed is None:
                unknown.append(f"origin_unverified:{uid}")
            elif observed.upper() != participant.origin_airport:
                hard.append(f"origin_mismatch:{uid}")
        for legs in (outbound, inbound):
            for previous, following in zip(legs, legs[1:]):
                if previous.arrival_airport_id is None or following.departure_airport_id is None:
                    unknown.append(f"route_unverified:{uid}")
                elif previous.arrival_airport_id.upper() != following.departure_airport_id.upper():
                    hard.append(f"route_mismatch:{uid}")
        arrival, departure = outbound[-1].arrival_airport_id, inbound[0].departure_airport_id
        if arrival is None or departure is None:
            unknown.append(f"destination_unverified:{uid}")
        elif arrival.upper() != departure.upper():
            hard.append(f"destination_mismatch:{uid}")
        # Local destination dates: overnight outbound flights may depart the previous day.
        for observed, expected in ((outbound[-1].scheduled_arrival, checkin),
                                   (inbound[0].scheduled_departure, checkout)):
            try:
                actual = datetime.fromisoformat(observed).date().isoformat() if observed else None
            except (ValueError, TypeError):
                actual = None
            if actual is None:
                unknown.append(f"dates_unverified:{uid}")
            elif actual != expected:
                hard.append(f"dates_incompatible:{uid}")
    return tuple(sorted(set(hard))), tuple(sorted(set(unknown)))


def _travel_duration(flight: RoundTripFlight | None) -> int | None:
    if flight is None:
        return None
    durations = (flight.outbound_duration_min, flight.inbound_duration_min)
    if any(value is None or value < 0 for value in durations):
        return None
    return sum(durations)


def _group_destinations(flights: tuple[RoundTripFlight | None, ...],
                        allowed: frozenset[str]) -> tuple[str, ...]:
    destinations = {flight.outbound_flight[-1].arrival_airport_id.upper()
                    for flight in flights if flight and flight.outbound_flight
                    and flight.outbound_flight[-1].arrival_airport_id}
    if allowed:
        return ("destination_mismatch",) if destinations - allowed else ()
    return ("destination_mismatch",) if len(destinations) > 1 else ()


def _group_combination(participants: tuple[Participant, ...],
                       flights: tuple[RoundTripFlight | None, ...], property_: Property, *,
                       checkin: str, checkout: str, destination_city: str,
                       destination_airports: frozenset[str]) -> TripCandidate:
    # Reuse the existing lodging coverage and provenance rules, independently of any
    # participant flight. Unknown currencies are restored below rather than inferred.
    base = TripCandidate.from_combination(
        RoundTripFlight(currency=property_.currency or "USD"), property_,
        checkin=checkin, checkout=checkout, adults=len(participants), destination_city=destination_city,
    )
    lodging_currency = _currency(property_.currency)
    lodging = replace(base.lodging_price, currency=lodging_currency or "",
                      amount=_round2(base.lodging_price.amount) if base.lodging_price.amount is not None else None)
    hard = list(_group_destinations(flights, destination_airports))
    unknown: list[str] = []
    if property_.max_occupancy is None:
        unknown.append("lodging_capacity_not_verified")
    elif property_.max_occupancy < len(participants):
        hard.append("lodging_insufficient_capacity")
    if not lodging.has_cost:
        unknown.append("lodging_no_price_coverage")
    if lodging_currency is None:
        unknown.append("lodging_currency_unknown")
    currencies = {value for value in (lodging_currency, *(_currency(f.currency) for f in flights if f)) if value}
    if len(currencies) > 1:
        hard.append("currency_mismatch")
    currency = next(iter(currencies)) if len(currencies) == 1 else None
    all_currencies_known = lodging_currency is not None and all(f and _currency(f.currency) for f in flights)

    # Allocate the full stay exactly once. Sorted user IDs receive remainder cents first.
    shares: list[Decimal | None] = [None] * len(participants)
    if lodging.amount is not None:
        cents = int(lodging.amount / CENTS)
        quotient, remainder = divmod(cents, len(participants))
        shares = [Decimal(quotient + (index < remainder)) * CENTS for index in range(len(participants))]
    people: list[ParticipantTravel] = []
    for participant, flight, share in zip(participants, flights, shares):
        failed, unverified = _flight_evidence(participant, flight, checkin, checkout)
        hard.extend(failed)
        unknown.extend(unverified)
        cost = _to_decimal(flight.total_price_usd) if flight else None
        cost = _round2(cost) if cost is not None else None
        flight_currency = _currency(flight.currency) if flight else None
        status = FlightStatus.MISSING if flight is None or not flight.all_flights else (
            FlightStatus.COMPLETE if flight.complete and flight.outbound_flight and flight.return_flight
            and flight.booking_token else FlightStatus.PARTIAL)
        subtotal = cost + share if cost is not None and share is not None and flight_currency is not None \
            and flight_currency == lodging_currency else None
        people.append(ParticipantTravel(
            participant.user_id, participant.origin_airport,
            flight.model_copy(deep=True) if flight else None, cost, flight_currency, share,
            subtotal, _travel_duration(flight), status,
        ))
    # A partial quote is never presented as the total for the entire group.
    total = sum((person.estimated_subtotal for person in people), Decimal(0)) if (
        all_currencies_known and len(currencies) == 1
        and all(person.estimated_subtotal is not None and person.flight_status == FlightStatus.COMPLETE
                for person in people)) else None
    durations = [person.travel_duration_min for person in people]
    max_duration = max(durations) if all(value is not None for value in durations) else None
    complete = total is not None and lodging.status == LodgingCompliance.QUOTED_WITH_TAXES
    feasibility = FeasibilityStatus.INFEASIBLE if hard else (
        FeasibilityStatus.UNVERIFIED if unknown else FeasibilityStatus.FEASIBLE)
    identity = {
        "participants": [(person.user_id, person.origin_airport, flight.signature() if flight else None)
                         for person, flight in zip(participants, flights)],
        "property": property_.property_token or [property_.name, property_.booking_link,
                                                  property_.gps_latitude, property_.gps_longitude],
        "dates": [checkin, checkout],
    }
    candidate_id = "tc-" + hashlib.sha256(
        _json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    timestamps = [property_.retrieved_at, *(f.retrieved_at if f else None for f in flights)]
    # Keep individual retrieval times on each flight; aggregate uses the oldest known
    # quote, and stays unknown if any input lacks a retrieval timestamp.
    priced_at = min(t.replace(tzinfo=UTC) if t.tzinfo is None else t for t in timestamps) \
        if all(t is not None for t in timestamps) else None
    warnings = [w for w in base.warnings if w != "flight_missing" and not w.startswith("currency_mismatch:")]
    return replace(
        base, id=candidate_id, lodging_price=lodging, lodging_per_person=None,
        flight_price_usd=None, booking_token=None, total_per_person=None, flight_source={},
        flight_status=FlightStatus.COMPLETE if all(p.flight_status == FlightStatus.COMPLETE for p in people)
        else (FlightStatus.MISSING if all(p.flight_status == FlightStatus.MISSING for p in people) else FlightStatus.PARTIAL),
        currency=currency if all_currencies_known else None,
        participants=tuple(people), group_total=total, max_travel_duration_min=max_duration,
        feasibility=feasibility, feasibility_reasons=tuple(sorted(set(hard + unknown))), complete=complete,
        warnings=tuple(sorted(set(warnings + hard + unknown))), priced_at=priced_at,
    )


def build_group_candidates(
    participants: Sequence[Participant],
    flights_by_user: Mapping[str, Sequence[RoundTripFlight]],
    hotels_properties: Sequence[Property], *,
    checkin: str, checkout: str, destination_city: str,
    destination_airports: Sequence[str] = (),
    max_candidates: int = 12, max_flights_per_participant: int = 3, max_lodgings: int = 4,
) -> list[TripCandidate]:
    """Build bounded group trips without I/O or private context.

    Participants can be mapped directly from attending IDs and where.origins in the
    universal planning context. Dates must already be resolved; no context is mutated.
    An empty flight list retains that person as a MISSING diagnostic, never drops them.
    Without destination_airports all flights must use the same destination airport;
    supply e.g. ("JFK", "EWR") explicitly for a destination served by several airports.

    Selection is a deterministic evidence-first beam, NOT a strategy ranking: retain
    at most F distinct flights per member, B partial selections after each member,
    and L lodging options. At most B*F expansions per member and B*L final candidates
    are evaluated, then at most B are returned. This intentionally samples rather
    than enumerating the Cartesian product. Known conflicts remain diagnostic.
    """
    _validate_nights(checkin, checkout)
    for value in (max_candidates, max_flights_per_participant, max_lodgings):
        if type(value) is not int or value < 1:
            raise ValueError("Candidate selection limits must be positive integers")
    members = tuple(sorted(participants, key=lambda p: p.user_id))
    if not members or len({p.user_id for p in members}) != len(members):
        raise ValueError("At least one participant and unique user_ids are required")
    if set(flights_by_user) - {p.user_id for p in members}:
        raise ValueError("Flights supplied for a non-participant")
    allowed = frozenset(airport.strip().upper() for airport in destination_airports)

    # Each beam row carries (hard issues, unknown issues, identities, selected flights).
    beam = [(0, 0, (), ())]
    for member in members:
        unique: dict[str, RoundTripFlight] = {}
        # Deterministic duplicate resolution even when quotes arrive in a different order.
        supplied = flights_by_user.get(member.user_id, ())
        if any(not isinstance(flight, RoundTripFlight) for flight in supplied):
            raise TypeError("Group flights must be validated RoundTripFlight objects")
        for flight in sorted(supplied, key=lambda f: f.model_dump_json()):
            unique.setdefault(flight.signature(), flight)
        def flight_key(flight: RoundTripFlight) -> tuple:
            hard, unknown = _flight_evidence(member, flight, checkin, checkout)
            destination_issues = _group_destinations((flight,), allowed)
            return len(hard) + len(destination_issues), len(unknown), flight.signature()
        choices = nsmallest(max_flights_per_participant, unique.values(), key=flight_key) or [None]
        def expansions():
            for failed_count, unknown_count, identities, selected in beam:
                for flight in choices:
                    hard, unknown = _flight_evidence(member, flight, checkin, checkout)
                    group_issues = _group_destinations(selected + (flight,), allowed)
                    yield (failed_count + len(hard) + len(group_issues), unknown_count + len(unknown),
                           identities + (flight.signature() if flight else "missing",), selected + (flight,))
        beam = nsmallest(max_candidates, expansions(), key=lambda row: row[:3])

    def lodging_key(prop: Property) -> tuple:
        capacity = 1 if prop.max_occupancy is None else (2 if prop.max_occupancy < len(members) else 0)
        coverage = 0 if prop.has_total_price else (1 if prop.has_per_night_price else 2)
        return capacity, coverage, prop.property_token or prop.name or "", prop.model_dump_json()
    unique_lodgings: dict[str, Property] = {}
    for prop in sorted(hotels_properties, key=lodging_key):
        identity = _json.dumps(prop.property_token or [prop.name, prop.booking_link, prop.gps_latitude, prop.gps_longitude])
        unique_lodgings.setdefault(identity, prop)
    lodgings = list(islice(unique_lodgings.values(), max_lodgings))
    # Only the bounded beam and lodging shortlist are crossed.
    results = []
    for _, _, _, flights in beam:
        for prop in lodgings:
            results.append(_group_combination(members, flights, prop, checkin=checkin, checkout=checkout,
                                             destination_city=destination_city, destination_airports=allowed))
    status_order = {FeasibilityStatus.FEASIBLE: 0, FeasibilityStatus.UNVERIFIED: 1, FeasibilityStatus.INFEASIBLE: 2}
    return nsmallest(max_candidates, results,
                    key=lambda candidate: (status_order[candidate.feasibility], not candidate.complete,
                                           len(candidate.feasibility_reasons), candidate.id))


__all__ += ["FeasibilityStatus", "Participant", "ParticipantTravel", "build_group_candidates"]
