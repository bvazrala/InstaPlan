"""The two kinds of context an AI model can receive.

GroupContext holds only what every member of the chat can already see. It is the ONLY input the Muse
prompt builders accept, so a prompt injection in the group chat ("tell me everyone's budget") has nothing to leak.

PrivateContext holds one member's private data. Only Gemini (private check-ins) and pure logic receive it.
Its repr is redacted so it never ends up in logs or tracebacks.
"""

from pydantic import BaseModel, ConfigDict

from app.schemas import PrivatePrefsData


class PrivacyViolation(Exception):
    """Raised when private data is about to cross into a group-facing path."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class GroupMember(_Frozen):
    id: str
    name: str
    home_airport: str | None = None


class GroupMessage(_Frozen):
    id: str
    sender_name: str
    text: str


class GroupFact(_Frozen):
    field: str
    value: str
    by: str | None = None


class GroupContext(_Frozen):
    trip_id: str | None
    members: tuple[GroupMember, ...]
    recent_messages: tuple[GroupMessage, ...]
    facts: tuple[GroupFact, ...] = ()


class PrivateContext(_Frozen):
    trip_id: str
    user_id: str
    first_name: str
    prefs: PrivatePrefsData
    suggested_ceiling: float | None = None

    def __repr__(self) -> str:
        return "PrivateContext(<redacted>)"

    __str__ = __repr__


def require_group_context(ctx: object) -> GroupContext:
    """Call at the top of every Muse prompt builder."""
    if not isinstance(ctx, GroupContext):
        raise PrivacyViolation(f"Muse prompts accept GroupContext only, got {type(ctx).__name__}")
    return ctx


def require_private_context(ctx: object) -> PrivateContext:
    if not isinstance(ctx, PrivateContext):
        raise PrivacyViolation(f"Expected PrivateContext, got {type(ctx).__name__}")
    return ctx
