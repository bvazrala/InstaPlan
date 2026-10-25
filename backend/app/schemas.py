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
    demo_speaker_id: str | None = None
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
    acknowledge_capacity: bool = False


class TravelLeg(ApiModel):
    id: str
    origin: str
    mode: str  # "Flight" | "Drive"
    hours: float | None
    cost: float | None
    lodging_allocation: float | None = None
    subtotal: float | None = None


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
    cats: dict[str, float | None]
    fairest_rank: int
    people: list[TravelLeg]
    hue: int = 260
    listing_url: str | None = None
    priced_at: datetime | None = None
    currency: str = "USD"
    group_total: float | None = None
    lodging_total: float | None = None
    max_travel_hours: float | None = None
    duration_basis: str = "round_trip"
    price_coverage: str = "unknown"
    feasibility: str = "unverified"
    pick_eligible: bool = False
    capacity_ack_required: bool = False
    warnings: list[str] = []
    cost_scope: str = "flights_and_lodging"


from app.logic.planning import PlanningInput


class GenerateIn(ApiModel):
    inputs: PlanningInput | None = None


class GenerationOut(ApiModel):
    status: str = "idle"
    run_id: str | None = None
    message: str | None = None
    missing: list[str] = []
    inputs: PlanningInput | None = None
    partial: bool = False
    option_count: int = 0


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

class PrivateOrigin(ApiModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    label: str = Field(min_length=1, max_length=120)


class PrivatePrefsData(ApiModel):
    """One member's private answers. Stored encrypted; returned only to its owner."""
    origin_location: PrivateOrigin | None = None
    budget_cap: float | None = Field(default=None, ge=0, allow_inf_nan=False)
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


# Unified public planner. Internal listener state and private preferences never appear here.
from typing import Any, Literal

class PlannerCreate(ApiModel):
    title: str = Field(min_length=1, max_length=120)
    topic: Literal["Dining", "Travel", "Entertainment"]
    location: str = Field(default="", max_length=200)
    timezone: str = "UTC"

class PlannerEdit(ApiModel):
    revision: int
    field: str
    value: Any = None
    demo_speaker_id: str | None = None

class PlannerVote(ApiModel):
    revision: int
    approve: bool
    demo_speaker_id: str | None = None

class PlannerTime(ApiModel):
    flexibility: dict[str, list[dict[str, str]] | None] = {}
    agreed: dict[str, str | None] | None = None

class PlannerWhere(ApiModel):
    destination: dict[str, str | float | None] | None = None
    destination_hint: str | None = None
    search_area: str | None = None
    origins: dict[str, str] = {}

class PlannerTemplate(ApiModel):
    title: str
    topic: Literal["Dining", "Travel", "Entertainment"]
    when: PlannerTime
    where: PlannerWhere
    preferences: dict[str, list[str]] = {}
    hard_constraints: dict[str, list[str]] = {}
    cluster: dict[str, str | list[str]] = {}
    sources: dict[str, str] = {}

class PlannerAttendance(ApiModel):
    status: Literal["going", "conditional", "not_going"]
    condition: str | None = None
    inferred: bool

class PlannerPoll(ApiModel):
    eligible: list[str]
    approvals: list[str]
    changes: list[str]
    required: int
    threshold: float
    ready: bool

class VenueOut(ApiModel):
    fit: float | None = None
    id: str
    title: str
    address: str | None = None
    rating: float | None = None
    price_level: str | None = None
    url: str | None = None
    provider: str = "SerpApi Google Maps"
    retrieved_at: datetime
    evidence: list[str] = []
    warnings: list[str] = []
    pick_eligible: bool = True

class TravelRecommendations(ApiModel):
    kind: Literal["travel"] = "travel"
    options: list[OptionOut] = []

class VenueRecommendations(ApiModel):
    kind: Literal["venues"] = "venues"
    venues: list[VenueOut] = []

class PlannerOut(ApiModel):
    trip_id: str
    title: str
    topic: Literal["Dining", "Travel", "Entertainment"]
    timezone: str
    revision: int
    approval_revision: int
    status: Literal["collecting", "approved", "picked"]
    template: PlannerTemplate
    attendance: dict[str, PlannerAttendance]
    poll: PlannerPoll
    listening: Literal["idle", "queued", "listening", "failed"]
    missing: list[str]
    generation: GenerationOut
    recommendations: TravelRecommendations | VenueRecommendations = Field(discriminator="kind")
    provenance: dict[str, str | None] = {}  # source message id to public speaker id
    picked_id: str | None = None
    priced_members: list[str] = []

class PlacesQuery(ApiModel):
    query: str = Field(min_length=2, max_length=160)
    session_token: str = Field(min_length=16, max_length=80)

class PlaceSelection(ApiModel):
    place_id: str = Field(min_length=1, max_length=300)
    session_token: str = Field(min_length=16, max_length=80)
    revision: int
