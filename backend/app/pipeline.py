"""What happens after group events: trip-intent offers, fact extraction, option generation.
Group-side steps only ever build a GroupContext (from group tables) for Muse."""

import logging

from fastapi.concurrency import run_in_threadpool
from sqlmodel import Session, select

from app.config import get_settings
from app.db import engine
from app.integrations import muse
from app.models import Fact, Message, Trip, User
from app.privacy.access import member_ids
from app.privacy.context import GroupContext, GroupFact, GroupMember, GroupMessage
from app.realtime import hub
from app.schemas import FactOut

log = logging.getLogger(__name__)


def open_trip(session: Session, chat_id: str) -> Trip | None:
    return session.exec(
        select(Trip).where(Trip.chat_id == chat_id, Trip.stage != "settle").order_by(Trip.created_at.desc())  # type: ignore[attr-defined]
    ).first()


def group_context(session: Session, chat_id: str, trip: Trip | None, limit: int = 30) -> GroupContext:
    """Built only from group tables (User public fields, Message, Fact). Private tables are never read here."""
    users = {u.id: u for u in session.exec(select(User).where(User.id.in_(member_ids(session, chat_id))))}  # type: ignore[attr-defined]
    msgs = session.exec(
        select(Message).where(Message.chat_id == chat_id).order_by(Message.sent_at.desc()).limit(limit)  # type: ignore[attr-defined]
    ).all()
    facts = session.exec(select(Fact).where(Fact.trip_id == trip.id)).all() if trip else []
    name = lambda uid: users[uid].display_name if uid in users else "Trip assistant"
    return GroupContext(
        trip_id=trip.id if trip else None,
        members=tuple(GroupMember(id=u.id, name=u.display_name, home_airport=u.home_airport) for u in users.values()),
        recent_messages=tuple(GroupMessage(id=m.id, sender_name=name(m.sender_id), text=m.body) for m in reversed(msgs)),
        facts=tuple(GroupFact(field=f.field, value=f.value, by=f.member_id) for f in facts),
    )


async def on_group_message(chat_id: str, message_id: str) -> None:
    """Runs after every group message (R2, R3). Failures are logged, never shown in the chat."""
    try:
        with Session(engine) as session:
            msg = session.get(Message, message_id)
            if msg is None or msg.sender_id is None:
                return
            trip = open_trip(session, chat_id)
            if trip is None:
                if muse.detect_trip_intent(msg.body):
                    await hub.to_chat(chat_id, {"type": "trip.offer", "chatId": chat_id})
                return
            if trip.stage != "collecting" or not get_settings().muse_api_key:
                return
            ctx = group_context(session, chat_id, trip)
            new = next(m for m in ctx.recent_messages if m.id == msg.id)
            for f in await run_in_threadpool(muse.extract_facts, ctx, new):
                fact = Fact(trip_id=trip.id, member_id=f.member_id, field=f.field, value=f.value,
                            score=f.score, required=f.required, source_message_id=msg.id, created_by=msg.sender_id)
                session.add(fact)
                session.commit()
                await hub.to_chat(chat_id, {"type": "fact.updated", "tripId": trip.id,
                                            "fact": FactOut.model_validate(fact).model_dump(by_alias=True)})
    except Exception:
        log.exception("group message pipeline failed")


def generate_options(session: Session, trip: Trip) -> None:
    """R12–R14. Build order, each step its own function:
    1. Shortlist 6–8 destinations from the trip facts (Muse, GroupContext only).
    2. Price travel per member: serpapi_client.flights (or drive cost = miles ÷ mpg × gas price).
    3. Price lodging: serpapi_client.lodging; divide by head count.
    4. Estimate daily spend from serpapi_client.places price levels; label it an estimate.
    5. Group fit per option and category: logic.fit.fit_score over facts + private scores.
    6. Load each member's ceiling from PrivatePrefs (decrypt), and only if privacy.access.private_budgets_allowed:
       logic.ranking.fairest drops over-budget options silently and returns ranks.
    7. Save TripOption rows with group-safe data only (schemas.OptionOut), then broadcast {"type": "options.ready"}.
    """
    raise NotImplementedError("Option generation is the data-and-ranking workstream (see docstring)")
