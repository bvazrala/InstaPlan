"""What happens after group events: trip-intent offers, fact extraction, option generation.
Group-side steps only ever build a GroupContext (from group tables) for Muse."""

import logging

from fastapi.concurrency import run_in_threadpool
from sqlmodel import Session, select

from app.config import get_settings
from app.db import engine
from app.integrations import muse_group
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
        facts=tuple(GroupFact(id=f.id, field=f.field, value=f.value, by=f.member_id, score=f.score, required=f.required) for f in facts),
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
                if muse_group.detect_trip_intent(msg.body):
                    await hub.to_chat(chat_id, {"type": "trip.offer", "chatId": chat_id})
                return
            from app.logic.planner_service import active
            if active(session, chat_id):
                return  # durable unified listener is queued by message persistence
            if trip.stage != "collecting" or not get_settings().muse_api_key:
                return
            ctx = group_context(session, chat_id, trip)
            new = next(m for m in ctx.recent_messages if m.id == msg.id)
            for f in await run_in_threadpool(muse_group.extract_facts, ctx, new):
                fact = Fact(trip_id=trip.id, member_id=f.member_id, field=f.field, value=f.value,
                            score=f.score, required=f.required, source_message_id=msg.id, created_by=msg.sender_id)
                session.add(fact)
                session.commit()
                await hub.to_chat(chat_id, {"type": "fact.updated", "tripId": trip.id,
                                            "fact": FactOut.model_validate(fact).model_dump(by_alias=True)})
    except Exception:
        log.exception("group message pipeline failed")


def generate_options(session: Session, trip: Trip, *, run_id: str | None = None, client=None):
    """Resolve -> fetch -> pure candidates -> private-boundary service -> atomic safe publication."""
    from sqlalchemy import update
    from sqlmodel import delete
    from app.integrations.serpapi_client import SerpApiClient
    from app.logic.candidates import Participant, build_group_candidates
    from app.logic.generation import ACTIVE, finish_state, recent, revision, start_run, utcnow
    from app.logic.option_service import evaluate_options
    from app.logic.planning import PlanningInput, known_inputs
    from app.models import OptionGeneration, TripOption, TripVote

    from app.models import PlannerSession
    from app.logic.planner_recommendations import travel_inputs, generate_venues
    planner = session.get(PlannerSession, trip.id)
    if planner and planner.status != 'approved':
        return False
    if run_id is None:
        run, started = start_run(session, trip)
        if not started:
            return False
        run_id = run.run_id
    run = session.get(OptionGeneration, trip.id)
    if run is None or run.run_id != run_id:
        return False
    if planner and planner.topic != 'Travel':
        return generate_venues(session, trip, planner, run_id, client)
    if not recent(run) or trip.stage not in {"checkin", "options", "confirmed"}:
        finish_state(session, trip.id, run_id, "failed", {"message": "Trip state changed. Please retry."})
        return False
    ctx = group_context(session, trip.chat_id, trip)
    declines = {vote.user_id for vote in session.exec(select(TripVote).where(
        TripVote.trip_id == trip.id, TripVote.going == False)).all()}
    members = [member for member in ctx.members if member.id in planner.approved_members] if planner else [member for member in ctx.members if member.id not in declines]
    ids = {member.id for member in members}
    inputs = travel_inputs(planner) if planner else known_inputs(ctx)
    if not planner and get_settings().muse_api_key:
        try:
            resolved = muse_group.resolve_planning(ctx)
            valid_facts = {fact.id for fact in ctx.facts}
            valid_rule = lambda rule: bool(rule.source_fact_ids) and set(rule.source_fact_ids) <= valid_facts \
                and getattr(rule, "member_id", None) in (None, *ids)
            resolved.destinations = [dest for dest in resolved.destinations if valid_rule(dest)]
            resolved.preferences = [pref for pref in resolved.preferences if valid_rule(pref)]
            resolved.constraints = [rule for rule in resolved.constraints if valid_rule(rule)]
            # Retain deterministic explicit restrictions if the model omitted them.
            keys = {(rule.kind, rule.member_id, tuple(rule.source_fact_ids)) for rule in resolved.constraints}
            covered = {source for rule in resolved.constraints for source in rule.source_fact_ids}
            resolved.constraints.extend(rule for rule in inputs.constraints
                if (rule.kind, rule.member_id, tuple(rule.source_fact_ids)) not in keys
                and not (rule.kind == "unsupported" and rule.source_fact_ids and set(rule.source_fact_ids) <= covered))
            resolved.origins = {**inputs.origins, **resolved.origins}
            inputs = resolved
        except Exception:
            # Exact public inputs still work when language resolution is unavailable.
            pass
    overrides = PlanningInput.model_validate(run.result["inputs"]) if run.result.get("inputs") else None
    if overrides:
        # Browser corrections can change public search values, never erase server-side constraints.
        inputs = inputs.model_copy(update={
            "destinations": overrides.destinations or inputs.destinations,
            "checkin": overrides.checkin or inputs.checkin, "checkout": overrides.checkout or inputs.checkout,
            "origins": {**inputs.origins, **overrides.origins},
        })
    inputs.origins = {uid: origin for uid, origin in inputs.origins.items() if uid in ids}
    inputs.constraints = [rule for rule in inputs.constraints if rule.member_id is None or rule.member_id in ids]
    inputs.preferences = [pref for pref in inputs.preferences if pref.member_id is None or pref.member_id in ids]
    missing = inputs.missing(sorted(ids)) if ids else ["participants"]
    public_inputs = inputs.model_dump(mode="json", by_alias=True)
    if missing:
        finish_state(session, trip.id, run_id, "needs_input", {"inputs": public_inputs, "missing": missing,
                     "message": "Confirm the missing trip details before searching."})
        return False
    # Persist only public resolved inputs while releasing the transaction during HTTP work.
    changed = session.execute(update(OptionGeneration).where(
        OptionGeneration.trip_id == trip.id, OptionGeneration.run_id == run_id,
        OptionGeneration.status.in_(ACTIVE)).values(status="generating", result={"inputs": public_inputs}))
    session.commit()
    if changed.rowcount != 1:
        return False
    client = client or SerpApiClient()
    candidates = []
    partial = False
    members = sorted(members, key=lambda member: member.id)
    participants = [Participant(member.id, inputs.origins[member.id]) for member in members]
    for destination in inputs.destinations[:6]:
        if client.requests >= client.settings.serpapi_request_limit:
            partial = True
            break
        flights, properties, failed = client.collect(
            inputs.origins.values(), destination, inputs.checkin.isoformat(), inputs.checkout.isoformat(), len(participants))
        partial = partial or failed
        by_user = {member.id: flights.get(inputs.origins[member.id], []) for member in members}
        candidates.extend(build_group_candidates(
            participants, by_user, properties, checkin=inputs.checkin.isoformat(), checkout=inputs.checkout.isoformat(),
            destination_city=destination.name, destination_airports=destination.airports,
        ))
    options = evaluate_options(session, trip.id, candidates, inputs)
    if partial and not options:
        finish_state(session, trip.id, run_id, "failed", {"message": "Travel prices could not be retrieved. Please retry.", "partial": True})
        return False
    # Lock the trip before publication; stale workers may not replace a newer generation.
    session.expire_all()
    current = session.exec(select(Trip).where(Trip.id == trip.id).with_for_update()).one()
    run = session.get(OptionGeneration, trip.id)
    if run.run_id != run_id:
        session.rollback()
        return False
    if not recent(run) or current.stage not in {"checkin", "options", "confirmed"}:
        session.rollback()
        finish_state(session, trip.id, run_id, "failed", {"message": "Trip state changed. Please retry."})
        return False
    if revision(session, current) != run.revision:
        finish_state(session, trip.id, run_id, "failed", {"message": "Trip details changed. Please generate options again."})
        return False
    # Acquire the lease in the same transaction as replacing the result set.
    changed = session.execute(update(OptionGeneration).where(
        OptionGeneration.trip_id == trip.id, OptionGeneration.run_id == run_id,
        OptionGeneration.status.in_(ACTIVE)).values(status="ready", published_revision=run.revision, updated_at=utcnow(), result={
            "inputs": public_inputs, "partial": partial, "option_count": len(options),
            "message": "Some travel searches were unavailable." if partial else None}))
    if changed.rowcount != 1:
        session.rollback()
        return False
    session.exec(delete(TripOption).where(TripOption.trip_id == trip.id))
    for option in options:
        session.add(TripOption(id=option.id, trip_id=trip.id, fairest_rank=option.fairest_rank,
                              data=option.model_dump(mode="json")))
    current.stage = "options"
    current.picked_option_id = None
    session.add(current)
    session.commit()
    return True
