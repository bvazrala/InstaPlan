"""Option cost math and the fairest ranking (R12, R13).

Burden = a member's total cost ÷ their private budget ceiling. It is computed here and never leaves this
module: callers get back which options survive and their fairest rank. Sending the burden ratio itself to the
browser would reveal the tightest budget whenever costs are similar.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PricedOption:
    id: str
    travel_cost: Mapping[str, float]  # member id → round-trip travel cost
    travel_hours: Mapping[str, float]  # member id → one-way travel time
    lodging_share: float  # per person, whole stay
    daily: float  # per person per day estimate
    nights: int


def person_total(o: PricedOption, member_id: str) -> float:
    cost = o.travel_cost.get(member_id)
    return cost + o.lodging_share + o.daily * o.nights if cost is not None else float("inf")


def group_total(o: PricedOption) -> float:
    return sum(person_total(o, m) for m in o.travel_cost) if o.travel_cost else float("inf")


def max_hours(o: PricedOption) -> float:
    return max((o.travel_hours.get(member) if o.travel_hours.get(member) is not None else float("inf")
                for member in o.travel_cost), default=float("inf"))


def _burden(o: PricedOption, ceilings: Mapping[str, float]) -> float:
    """Highest share of anyone's ceiling this option uses. Members without a ceiling don't constrain it."""
    shares = [person_total(o, m) / c if c > 0 else (float("inf") if person_total(o, m) > 0 else 0.0)
              for m, c in ceilings.items() if c is not None]
    return max(shares, default=0.0)


def fairest(options: Sequence[PricedOption], ceilings: Mapping[str, float]) -> tuple[list[PricedOption], dict[str, int]]:
    """Drops options that push anyone over their ceiling (silently: never say why or for whom),
    then ranks the rest by lowest highest burden. Returns (kept options, option id → rank starting at 1)."""
    kept = [o for o in options if _burden(o, ceilings) <= 1.0]
    order = sorted(kept, key=lambda o: (_burden(o, ceilings), group_total(o), o.id))
    return kept, {o.id: i + 1 for i, o in enumerate(order)}


from decimal import Decimal
from math import isfinite
from app.logic.candidates import TripCandidate


def _candidate_cost(candidate: TripCandidate) -> Decimal:
    return candidate.group_total if candidate.group_total is not None else Decimal("Infinity")


def _candidate_duration(candidate: TripCandidate) -> float:
    return candidate.max_travel_duration_min if candidate.max_travel_duration_min is not None else float("inf")


def _candidate_burden(candidate: TripCandidate, ceilings: Mapping[str, Decimal]) -> Decimal:
    shares = []
    for person in candidate.participants:
        ceiling = ceilings.get(person.user_id)
        if ceiling is None:
            continue
        total = person.estimated_subtotal
        if total is None or ceiling < 0 or (ceiling == 0 and total > 0):
            return Decimal("Infinity")
        shares.append(total / ceiling if ceiling else Decimal(0))
    return max(shares, default=Decimal(0))


def within_ceilings(candidate: TripCandidate, ceilings: Mapping[str, Decimal]) -> bool:
    return _candidate_burden(candidate, ceilings) <= 1


def rank_candidates(options: Sequence[TripCandidate], strategy: str = "balanced", *,
                    weight: float = 0.5, ceilings: Mapping[str, Decimal] | None = None) -> list[TripCandidate]:
    if strategy not in {"cheapest", "fastest", "balanced", "fairest"}:
        raise ValueError("Unknown ranking strategy")
    if not isfinite(weight) or not 0 <= weight <= 1:
        raise ValueError("weight must be between 0 and 1")
    ceilings = ceilings or {}
    options = [option for option in options if within_ceilings(option, ceilings)]
    costs, durations = [_candidate_cost(o) for o in options], [_candidate_duration(o) for o in options]
    def norm(value, values):
        if not isfinite(value):
            return float("inf")
        finite = [float(item) for item in values if isfinite(item)]
        if not finite or max(finite) == min(finite):
            return 0.0
        return (float(value) - min(finite)) / (max(finite) - min(finite))
    def key(option):
        cost, duration = _candidate_cost(option), _candidate_duration(option)
        if strategy == "cheapest" or (strategy == "fairest" and not ceilings):
            score = cost
        elif strategy == "fastest":
            score = duration
        elif strategy == "fairest":
            score = _candidate_burden(option, ceilings)
        else:
            # Missing either measurement remains unknown, even at the slider endpoints.
            score = weight * norm(cost, costs) + (1 - weight) * norm(duration, durations) \
                if isfinite(cost) and isfinite(duration) else float("inf")
        return score, cost if strategy == "fairest" else 0, option.id
    return sorted(options, key=key)


def cheapest(options):
    return rank_candidates(options, "cheapest")


def fastest(options):
    return rank_candidates(options, "fastest")


def balanced(options, weight=0.5):
    return rank_candidates(options, "balanced", weight=weight)
