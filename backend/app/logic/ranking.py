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
    return o.travel_cost.get(member_id, 0.0) + o.lodging_share + o.daily * o.nights


def group_total(o: PricedOption) -> float:
    return sum(person_total(o, m) for m in o.travel_cost)


def max_hours(o: PricedOption) -> float:
    return max(o.travel_hours.values(), default=0.0)


def _burden(o: PricedOption, ceilings: Mapping[str, float]) -> float:
    """Highest share of anyone's ceiling this option uses. Members without a ceiling don't constrain it."""
    shares = [person_total(o, m) / c for m, c in ceilings.items() if c and c > 0]
    return max(shares, default=0.0)


def fairest(options: Sequence[PricedOption], ceilings: Mapping[str, float]) -> tuple[list[PricedOption], dict[str, int]]:
    """Drops options that push anyone over their ceiling (silently: never say why or for whom),
    then ranks the rest by lowest highest burden. Returns (kept options, option id → rank starting at 1)."""
    kept = [o for o in options if _burden(o, ceilings) <= 1.0]
    order = sorted(kept, key=lambda o: (_burden(o, ceilings), group_total(o)))
    return kept, {o.id: i + 1 for i, o in enumerate(order)}
