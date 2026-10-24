"""Request and response shapes. JSON is camelCase to match frontend/lib/types.ts.
A field only reaches the browser if it is declared here, so review this file for leaks."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


# ── Group-visible ─────────────────────────────────────────────────────────────

class MemberOut(ApiModel):
    id: str
    name: str
    handle: str
    hue: int
    origin: str | None = None  # home airport


class ChatOut(ApiModel):
    id: str
    name: str
    group: bool
    members: list[str]


class MessageOut(ApiModel):
    id: str
    from_: str = Field(alias="from")  # user id, or "assistant"
    kind: str = "text"
    text: str
    sent_at: datetime


class SendMessageIn(ApiModel):
    text: str = Field(min_length=1, max_length=2000)


class TripOut(ApiModel):
    id: str
    chat_id: str
    stage: str
    picked_option_id: str | None = None
    yes_votes: int = 0
    member_count: int = 0
    checkins_done: int = 0  # a count only, never whose


class FactOut(ApiModel):
    id: str
    field: str
    value: str
    by: str | None = Field(default=None, validation_alias="member_id")
    src: str | None = Field(default=None, validation_alias="source_message_id")
    required: bool = False


class FactPatch(ApiModel):
    value: str = Field(min_length=1, max_length=200)


class VoteIn(ApiModel):
    going: bool


class PickIn(ApiModel):
    option_id: str


class TravelLeg(ApiModel):
    id: str
    origin: str
    mode: str  # "Flight" | "Drive"
    hours: float
    cost: float


class OptionOut(ApiModel):
    """Group-safe option. No burden ratio and no ceilings: only the fairest rank leaves the server."""
    id: str
    title: str
    place: str
    dates: str
    nights: int
    lodging: str
    lodging_share: float
    daily: float
    fit: float
    certainty: str
    cats: dict[str, float]
    fairest_rank: int
    people: list[TravelLeg]
    hue: int = 260
    listing_url: str | None = None
    priced_at: datetime | None = None


class ExpenseIn(ApiModel):
    description: str = Field(min_length=1, max_length=120)
    amount: float = Field(gt=0)


class ExpenseOut(ApiModel):
    id: str
    description: str
    payer_id: str
    amount: float


class TransferOut(ApiModel):
    from_: str = Field(alias="from")
    to: str
    amount: float


# ── Owner only ────────────────────────────────────────────────────────────────

class PrivatePrefsData(ApiModel):
    """One member's private answers. Stored encrypted; returned only to its owner."""
    budget_cap: float | None = None
    dietary: list[str] = []
    accessibility: list[str] = []
    no_gos: str = ""
    private_scores: dict[str, int] = {}  # item → -2..+2, e.g. {"Philadelphia": -2}


class CheckInMessageOut(ApiModel):
    id: str
    from_assistant: bool
    text: str
    sent_at: datetime


class BudgetSuggestionOut(ApiModel):
    amount: float
    reason: str
