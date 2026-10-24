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
