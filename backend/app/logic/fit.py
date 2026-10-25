"""Group fit score (R14): 0 = red, 50 = yellow, 100 = green.

fit = 50 + 25 × (0.8 × average + 0.2 × strongest objection), from per-member scores of -2..+2.
Mostly the group average, pulled down a little by the strongest objection, so one dislike lowers an item
without removing it. Hard restrictions (allergies, "I won't fly") are filters, never scores.
"""

from collections.abc import Sequence

AVERAGE_WEIGHT = 0.8
OBJECTION_WEIGHT = 0.2


def fit_score(scores: Sequence[int]) -> float:
    """`scores` has one entry per member: -2 strong dislike … +2 love; 0 = neutral or unknown."""
    if not scores:
        return 50.0
    avg = sum(scores) / len(scores)
    raw = 50 + 25 * (AVERAGE_WEIGHT * avg + OBJECTION_WEIGHT * min(scores))
    return round(max(0.0, min(100.0, raw)), 1)


def certainty(scores: Sequence[int], group_size: int) -> str:
    """How many members have weighed in, e.g. "3 of 5 weighed in"."""
    return f"{sum(1 for s in scores if s != 0)} of {group_size} weighed in"


from dataclasses import dataclass
from datetime import date
from statistics import mean
from app.logic.candidates import TripCandidate, FeasibilityStatus
from app.logic.planning import Constraint, Preference


@dataclass(frozen=True)
class CandidateFit:
    fit: float
    cats: dict[str, float | None]
    certainty: str
    violated: bool
    pick_eligible: bool
    capacity_ack_required: bool
    feasibility: str
    warnings: tuple[str, ...]


def _text(value: str) -> str:
    aliases = {"free wi-fi": "wifi", "free wifi": "wifi", "wi-fi": "wifi",
               "wheelchair-accessible": "wheelchair accessible", "swimming pool": "pool",
               "nyc": "new york city", "new york": "new york city", "la": "los angeles", "sf": "san francisco"}
    value = " ".join(value.casefold().split())
    return aliases.get(value, value)


def check_constraint(candidate: TripCandidate, constraint: Constraint) -> str:
    """verified / violated / unknown. Never guesses from missing evidence."""
    people = [p for p in candidate.participants if constraint.member_id is None or p.user_id == constraint.member_id]
    if not people:
        return "unknown"
    kind = constraint.kind
    if kind == "unsupported":
        return "unknown"
    if kind == "exclude_destination":
        if not constraint.value.strip():
            return "unknown"
        destinations = {_text(candidate.place)} | {f.flight.destination_id.casefold() for f in people
                                                     if f.flight and f.flight.destination_id}
        return "violated" if _text(constraint.value) in destinations else "verified"
    if kind == "flight_only":
        return "verified" if all(p.flight for p in people) else "unknown"
    if kind == "available_dates":
        if constraint.start is None or constraint.end is None:
            return "unknown"
        for person in people:
            if person.flight is None or not person.flight.outbound_flight or not person.flight.return_flight:
                return "unknown"
            try:
                from datetime import datetime
                start = datetime.fromisoformat(person.flight.outbound_flight[0].scheduled_departure).date()
                end = datetime.fromisoformat(person.flight.return_flight[-1].scheduled_arrival).date()
            except (ValueError, TypeError):
                return "unknown"
            if not constraint.start <= start <= end <= constraint.end:
                return "violated"
        return "verified"
    if kind == "max_duration":
        if constraint.limit is None or any(p.travel_duration_min is None for p in people):
            return "unknown"
        return "violated" if any(p.travel_duration_min > constraint.limit for p in people) else "verified"
    if kind == "max_stops":
        if constraint.limit is None or any(p.flight is None for p in people):
            return "unknown"
        return "violated" if any(max(len(p.flight.outbound_flight), len(p.flight.return_flight)) - 1 > constraint.limit
                                  for p in people) else "verified"
    if kind == "amenity":
        amenities = {_text(value) for value in candidate.lodging_amenities}
        # An absent amenity is not evidence of absence in a partial provider listing.
        return "verified" if constraint.value.strip() and _text(constraint.value) in amenities else "unknown"
    return "unknown"


def evaluate_fit(candidate: TripCandidate, preferences: Sequence[Preference] = (),
                 constraints: Sequence[Constraint] = ()) -> CandidateFit:
    states = [check_constraint(candidate, constraint) for constraint in constraints]
    violated = "violated" in states or candidate.feasibility == FeasibilityStatus.INFEASIBLE
    structural_unknown = any(reason != "lodging_capacity_not_verified" for reason in candidate.feasibility_reasons)
    unresolved = "unknown" in states or structural_unknown
    member_ids = [p.user_id for p in candidate.participants]
    category_scores = {}
    weighed_in = set()
    for category in ("Destination", "Lodging", "Travel"):
        tags = ({_text(candidate.place)} | {p.flight.destination_id.casefold() for p in candidate.participants
                                           if p.flight and p.flight.destination_id}) if category == "Destination" else (
            {_text(candidate.lodging_name), *(_text(a) for a in candidate.lodging_amenities)} if category == "Lodging"
            else {"flight", "flights", "fly"})
        per_member = []
        for uid in member_ids:
            matches = [preference.score for preference in preferences if preference.category == category
                       and preference.member_id in (None, uid) and _text(preference.value) in tags]
            per_member.append(mean(matches) if matches else 0)
            if matches:
                weighed_in.add(uid)
        category_scores[category] = fit_score(per_member)
    category_scores.update(Food=None, Activities=None)
    eligible = not violated and not unresolved and candidate.group_total is not None
    warnings = []
    if not candidate.capacity_verified:
        warnings.append("capacity_unverified")
    if unresolved:
        # No private rule, value or member identifier may be exposed here.
        warnings.append("requirements_unverified")
    if candidate.lodging_price.status.value == "estimated_before_taxes":
        warnings.append("lodging_estimated_before_taxes")
    return CandidateFit(round(mean(value for value in category_scores.values() if value is not None), 1),
                        category_scores, f"{len(weighed_in)} of {len(member_ids)} weighed in",
                        violated, eligible, eligible and not candidate.capacity_verified,
                        "infeasible" if violated else ("unverified" if unresolved or not candidate.capacity_verified else "feasible"),
                        tuple(warnings))
