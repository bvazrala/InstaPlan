"""Safe-to-spend ceiling from a member's Nessie account (R11). Plain math, not a model: it's someone's money.

ceiling = balance − bills due before the trip ends − cushion, rounded down to $10.
cushion = the larger of $100 or 15% of the balance. Tune during testing.
"""

from collections.abc import Sequence
from dataclasses import dataclass

MIN_CUSHION = 100.0
CUSHION_RATIO = 0.15


@dataclass(frozen=True)
class Bill:
    payee: str
    amount: float


@dataclass(frozen=True)
class Ceiling:
    amount: float
    bills_total: float
    cushion: float
    largest_bill: Bill | None


def safe_to_spend(balance: float, bills_before_trip: Sequence[Bill]) -> Ceiling:
    bills_total = sum(b.amount for b in bills_before_trip)
    cushion = max(MIN_CUSHION, CUSHION_RATIO * max(balance, 0.0))
    amount = max(0.0, balance - bills_total - cushion)
    largest = max(bills_before_trip, key=lambda b: b.amount, default=None)
    return Ceiling(amount=float(int(amount // 10) * 10), bills_total=bills_total, cushion=cushion, largest_bill=largest)


def default_reason(c: Ceiling) -> str:
    """One-line explanation. Muse may rephrase it in the private check-in, but only from these numbers."""
    if c.largest_bill:
        return f"{c.largest_bill.payee} (${c.largest_bill.amount:,.0f}) is due before the trip, so we kept a ${c.cushion:,.0f} cushion."
    return f"No bills are due before the trip; we kept a ${c.cushion:,.0f} cushion."
