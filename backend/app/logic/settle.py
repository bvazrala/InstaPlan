"""Settle up (R17): split shared expenses and suggest the fewest transfers. All amounts in cents."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Transfer:
    from_id: str
    to_id: str
    cents: int


def equal_split(amount_cents: int, member_ids: Sequence[str]) -> dict[str, int]:
    """Splits evenly; leftover cents go to the first members so shares always sum to the total."""
    base, extra = divmod(amount_cents, len(member_ids))
    return {m: base + (1 if i < extra else 0) for i, m in enumerate(member_ids)}


def net_balances(expenses: Iterable[tuple[str, int, dict[str, int]]]) -> dict[str, int]:
    """(payer, amount, split) per expense → member → net cents (positive = is owed money)."""
    net: dict[str, int] = {}
    for payer, amount, split in expenses:
        net[payer] = net.get(payer, 0) + amount
        for member, share in split.items():
            net[member] = net.get(member, 0) - share
    return net


def suggest_transfers(net: dict[str, int]) -> list[Transfer]:
    """Greedy: the biggest debtor pays the biggest creditor until everyone is even."""
    debtors = sorted(((-v, m) for m, v in net.items() if v < 0), reverse=True)
    creditors = sorted(((v, m) for m, v in net.items() if v > 0), reverse=True)
    out: list[Transfer] = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        owe, debtor = debtors[i]
        due, creditor = creditors[j]
        pay = min(owe, due)
        out.append(Transfer(debtor, creditor, pay))
        debtors[i] = (owe - pay, debtor)
        creditors[j] = (due - pay, creditor)
        if debtors[i][0] == 0:
            i += 1
        if creditors[j][0] == 0:
            j += 1
    return out
