"""Database tables. Private data has its own tables (PrivatePrefs, PrivateMessage) and is encrypted at rest,
so no group query can return it by accident. See docs/api-contract.md for what each API exposes."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _id() -> str:
    return uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


# ── People and chats ──────────────────────────────────────────────────────────

class User(SQLModel, table=True):
    id: str = Field(primary_key=True)  # Supabase Auth user id
    display_name: str
    handle: str
    home_airport: str | None = None
    hue: int = 260  # avatar color
    nessie_customer_id: str | None = None  # never returned to other users


class Chat(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    name: str
    is_group: bool = True


class ChatMember(SQLModel, table=True):
    chat_id: str = Field(foreign_key="chat.id", primary_key=True)
    user_id: str = Field(foreign_key="user.id", primary_key=True)


class Message(SQLModel, table=True):
    """Group messages only. Private assistant messages live in PrivateMessage."""
    id: str = Field(default_factory=_id, primary_key=True)
    chat_id: str = Field(foreign_key="chat.id", index=True)
    sender_id: str | None = Field(default=None, foreign_key="user.id")  # None = the trip assistant
    body: str
    sent_at: datetime = Field(default_factory=_now)


# ── Trips (group-visible) ─────────────────────────────────────────────────────

class Trip(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    chat_id: str = Field(foreign_key="chat.id", index=True)
    stage: str = "collecting"  # see app/logic/trip_state.py
    created_by: str = Field(foreign_key="user.id")
    picked_option_id: str | None = None
    created_at: datetime = Field(default_factory=_now)


class TripVote(SQLModel, table=True):
    trip_id: str = Field(foreign_key="trip.id", primary_key=True)
    user_id: str = Field(foreign_key="user.id", primary_key=True)
    going: bool


class Fact(SQLModel, table=True):
    """Something said in the group chat, e.g. field="Food", value="No seafood", score=-2."""
    id: str = Field(default_factory=_id, primary_key=True)
    trip_id: str = Field(foreign_key="trip.id", index=True)
    member_id: str | None = Field(default=None, foreign_key="user.id")  # None = applies to the whole group
    field: str
    value: str
    score: int | None = None  # -2..+2 preference toward `value`
    required: bool = False
    source_message_id: str | None = Field(default=None, foreign_key="message.id")
    created_by: str | None = Field(default=None, foreign_key="user.id")


class TripOption(SQLModel, table=True):
    """A priced option. `data` holds only group-safe fields (see schemas.OptionOut); no burden, no ceilings."""
    id: str = Field(default_factory=_id, primary_key=True)
    trip_id: str = Field(foreign_key="trip.id", index=True)
    data: dict[str, Any] = Field(sa_column=Column(JSON))
    fairest_rank: int
    priced_at: datetime = Field(default_factory=_now)


class Expense(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    trip_id: str = Field(foreign_key="trip.id", index=True)
    payer_id: str = Field(foreign_key="user.id")
    description: str
    amount_cents: int
    split_cents: dict[str, int] = Field(sa_column=Column(JSON))  # user_id → share
    nessie_transfer_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))


# ── Private (owner only, encrypted) ───────────────────────────────────────────

class PrivatePrefs(SQLModel, table=True):
    trip_id: str = Field(foreign_key="trip.id", primary_key=True)
    user_id: str = Field(foreign_key="user.id", primary_key=True)
    data_encrypted: str  # Fernet token of schemas.PrivatePrefsData JSON
    updated_at: datetime = Field(default_factory=_now)


class PrivateMessage(SQLModel, table=True):
    """The member's private check-in thread with the assistant."""
    id: str = Field(default_factory=_id, primary_key=True)
    trip_id: str = Field(foreign_key="trip.id", index=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    from_assistant: bool
    body_encrypted: str
    sent_at: datetime = Field(default_factory=_now)


# ── Server only ───────────────────────────────────────────────────────────────

class ApiCache(SQLModel, table=True):
    key: str = Field(primary_key=True)  # sha256 of provider + params
    response: dict[str, Any] = Field(sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=_now)


class OptionGeneration(SQLModel, table=True):
    """Server-owned state. Public status projection excludes the revision fingerprint."""
    trip_id: str = Field(foreign_key="trip.id", primary_key=True)
    run_id: str = Field(default_factory=_id)
    status: str = "idle"
    revision: str = ""
    published_revision: str = ""
    started_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    result: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class PlannerSession(SQLModel, table=True):
    trip_id: str = Field(foreign_key="trip.id", primary_key=True)
    title: str
    topic: str
    timezone: str = "UTC"
    revision: int = 0
    approval_revision: int = 0
    epoch: int = 0
    threshold: float = 0.5
    status: str = "collecting"
    template: dict[str, Any] = Field(sa_column=Column(JSON))
    internal: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    approved_members: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class PlannerApproval(SQLModel, table=True):
    trip_id: str = Field(foreign_key="trip.id", primary_key=True)
    revision: int = Field(primary_key=True)
    user_id: str = Field(foreign_key="user.id", primary_key=True)
    approve: bool


class ListeningBatch(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    trip_id: str = Field(foreign_key="trip.id", index=True)
    epoch: int
    message_ids: list[str] = Field(sa_column=Column(JSON))
    source_revisions: dict[str, int] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "queued"
    queued_at: datetime = Field(default_factory=_now)
    started_at: datetime | None = None
    lease_id: str | None = None


class VenueRecommendation(SQLModel, table=True):
    id: str = Field(primary_key=True)
    trip_id: str = Field(foreign_key="trip.id", index=True)
    revision: int
    data: dict[str, Any] = Field(sa_column=Column(JSON))

class WidgetItinerary(SQLModel, table=True):
    """Provider evidence for an owner's optional flight widget. Never serialized in shared options."""
    option_id: str = Field(primary_key=True)
    user_id: str = Field(foreign_key="user.id",primary_key=True)
    trip_id: str = Field(foreign_key="trip.id",index=True)
    data: dict[str, Any] = Field(sa_column=Column(JSON))


class DemoChatState(SQLModel, table=True):
    chat_id: str = Field(foreign_key="chat.id",primary_key=True)
    reset_at: datetime = Field(default_factory=_now)


class PublicProfile(SQLModel, table=True):
    user_id: str = Field(foreign_key="user.id",primary_key=True)
    avatar_url: str
