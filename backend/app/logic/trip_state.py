"""Trip stages and the moves allowed between them (matches frontend Stage, minus "idle" = no trip yet)."""

from enum import StrEnum


class Stage(StrEnum):
    COLLECTING = "collecting"
    VOTING = "voting"
    CONFIRMED = "confirmed"
    CHECKIN = "checkin"
    OPTIONS = "options"
    PICKED = "picked"
    SETTLE = "settle"


ALLOWED: dict[Stage, set[Stage]] = {
    Stage.COLLECTING: {Stage.VOTING},
    Stage.VOTING: {Stage.COLLECTING, Stage.CHECKIN},  # "no" returns to collecting
    Stage.CONFIRMED: {Stage.COLLECTING, Stage.OPTIONS},
    Stage.CHECKIN: {Stage.OPTIONS},
    Stage.OPTIONS: {Stage.PICKED},
    Stage.PICKED: {Stage.OPTIONS, Stage.SETTLE},  # "tweak" re-runs options
    Stage.SETTLE: set(),
}


class InvalidTransition(ValueError):
    pass


def advance(current: str, target: str) -> Stage:
    cur, nxt = Stage(current), Stage(target)
    if nxt not in ALLOWED[cur]:
        raise InvalidTransition(f"{cur} → {nxt} is not allowed")
    return nxt


def has_majority(yes_votes: int, group_size: int) -> bool:
    return yes_votes > group_size / 2
