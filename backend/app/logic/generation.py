"""Generation leases and public input revisions; private values never enter this module."""
import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from app.logic.option_service import private_revision
from app.models import PlannerSession, Fact, OptionGeneration, Trip, TripVote, User
from app.privacy.access import member_ids
from app.schemas import GenerationOut

ACTIVE = {"resolving", "generating"}


def utcnow():
    return datetime.now(UTC)


def recent(run):
    started = run.started_at.replace(tzinfo=UTC) if run.started_at.tzinfo is None else run.started_at
    return run.status in ACTIVE and utcnow() - started < timedelta(minutes=5)


def revision(session: Session, trip: Trip) -> str:
    ids = sorted(member_ids(session, trip.chat_id))
    facts = session.exec(select(Fact).where(Fact.trip_id == trip.id).order_by(Fact.id)).all()
    votes = session.exec(select(TripVote).where(TripVote.trip_id == trip.id).order_by(TripVote.user_id)).all()
    users = session.exec(select(User).where(User.id.in_(ids)).order_by(User.id)).all()
    value = {"members": ids, "origins": [(u.id, u.home_airport) for u in users],
             "facts": [f.model_dump(mode="json") for f in facts], "votes": [v.model_dump() for v in votes],
             "private_revision": private_revision(session, trip.id)}
    planner = session.get(PlannerSession, trip.id)
    if planner:
        value['planner'] = {'approval':planner.approval_revision,'epoch':planner.epoch,
                            'members':planner.approved_members,'pricing':planner.internal.get('pricing')}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def public_status(run: OptionGeneration | None) -> GenerationOut:
    if run is None:
        return GenerationOut()
    if run.status in ACTIVE and not recent(run):
        return GenerationOut(status="failed", run_id=run.run_id, message="Generation was interrupted. Please retry.")
    return GenerationOut.model_validate({**run.result, "status": run.status, "run_id": run.run_id})


def start_run(session: Session, trip: Trip, inputs=None):
    # A compare-and-swap lease works on SQLite and PostgreSQL, including multiple workers.
    old = session.get(OptionGeneration, trip.id)
    if old and recent(old):
        return old, False
    run_id = uuid4().hex
    current_revision = revision(session, trip)
    # Retain confirmed public search corrections while the underlying inputs match.
    saved_inputs = inputs.model_dump(mode="json") if inputs else (
        old.result.get("inputs") if old and old.revision == current_revision else None)
    values = dict(run_id=run_id, status="resolving", revision=current_revision,
                  started_at=utcnow(), updated_at=utcnow(),
                  result={"inputs": saved_inputs})
    if old:
        changed = session.execute(update(OptionGeneration).where(
            OptionGeneration.trip_id == trip.id, OptionGeneration.run_id == old.run_id,
            OptionGeneration.status == old.status, OptionGeneration.started_at == old.started_at).values(**values))
        if changed.rowcount != 1:
            session.rollback()
            session.expire_all()
            return session.get(OptionGeneration, trip.id), False
    else:
        session.add(OptionGeneration(trip_id=trip.id, **values))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return session.get(OptionGeneration, trip.id), False
    session.expire_all()
    return session.get(OptionGeneration, trip.id), True


def finish_state(session: Session, trip_id: str, run_id: str, status: str, result: dict) -> bool:
    changed = session.execute(update(OptionGeneration).where(
        OptionGeneration.trip_id == trip_id, OptionGeneration.run_id == run_id,
        OptionGeneration.status.in_(ACTIVE)).values(status=status, result=result, updated_at=utcnow()))
    session.commit()
    return changed.rowcount == 1
