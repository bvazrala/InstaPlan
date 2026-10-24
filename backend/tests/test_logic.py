"""Unit tests for the pure logic in app/logic/."""

import pytest

from app.logic.budget import Bill, default_reason, safe_to_spend
from app.logic.fit import certainty, fit_score
from app.logic.ranking import PricedOption, fairest, group_total
from app.logic.settle import equal_split, net_balances, suggest_transfers
from app.logic.trip_state import InvalidTransition, Stage, advance, has_majority


@pytest.mark.parametrize("scores, expected", [
    ([1, 1, 1, 1, 1], 75),      # all like it
    ([2, 2, 2, 2, -1], 73),     # four love it, one dislikes it
    ([0, 0, 0, 0, 0], 50),      # no opinions yet
    ([1, 1, 1, 1, -2], 48),     # one strong objection pulls it to yellow
    ([-1, -1, -1, 1, 1], 41),   # three dislike, two like
])
def test_fit_score_matches_requirements_table(scores, expected):
    assert fit_score(scores) == expected


def test_certainty_counts_who_weighed_in():
    assert certainty([1, 0, -2], 5) == "2 of 5 weighed in"


def _option(id_, travel, lodging=200.0, daily=80.0, nights=3):
    return PricedOption(id=id_, travel_cost=travel, travel_hours={m: 4.0 for m in travel},
                        lodging_share=lodging, daily=daily, nights=nights)


def test_fairest_drops_options_over_anyones_ceiling_and_ranks_the_rest():
    travel = {"a": 300.0, "b": 300.0, "c": 300.0}
    cheap, mid, pricey = _option("cheap", travel, 100), _option("mid", travel, 200), _option("pricey", travel, 600)
    kept, ranks = fairest([pricey, mid, cheap], {"a": 1000, "b": 800, "c": 2000})
    assert [o.id for o in kept] == ["mid", "cheap"]  # pricey (1140) exceeds b's 800
    assert ranks == {"cheap": 1, "mid": 2}


def test_group_total_sums_every_member():
    assert group_total(_option("x", {"a": 100.0, "b": 50.0}, lodging=10, daily=0)) == 170


def test_safe_to_spend_leaves_bills_and_cushion():
    c = safe_to_spend(1900, [Bill("Rent", 890)])
    assert c.amount == 720  # 1900 − 890 − 285 cushion, rounded down to $10
    assert "Rent" in default_reason(c)


def test_equal_split_sums_to_total():
    split = equal_split(1000, ["a", "b", "c"])
    assert sum(split.values()) == 1000 and max(split.values()) - min(split.values()) <= 1


def test_suggested_transfers_settle_everyone():
    net = net_balances([("maya", 86000, equal_split(86000, ["you", "maya", "alex", "sam"]))])
    transfers = suggest_transfers(net)
    assert {t.from_id for t in transfers} == {"you", "alex", "sam"}
    assert all(t.to_id == "maya" and t.cents == 21500 for t in transfers)


def test_stage_moves():
    assert advance("collecting", "voting") == Stage.VOTING
    with pytest.raises(InvalidTransition):
        advance("collecting", "options")
    assert has_majority(3, 4) and not has_majority(2, 4)
