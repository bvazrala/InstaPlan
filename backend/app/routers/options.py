"""Authorized option generation, status and privacy-safe result retrieval."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlmodel import Session, select

from app.auth import CurrentUser, get_current_user
from app.db import engine, get_session
from app.logic.generation import finish_state, public_status, start_run
from app.models import OptionGeneration, Trip, TripOption
from app.pipeline import generate_options
from app.privacy.access import require_trip_member
from app.realtime import hub
from app.schemas import GenerateIn, GenerationOut, OptionOut

router = APIRouter(tags=["options"])


@router.get("/trips/{trip_id}/options", response_model=list[OptionOut])
def list_options(trip_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    require_trip_member(session, trip_id, user)
    rows = session.exec(select(TripOption).where(TripOption.trip_id == trip_id).order_by(TripOption.fairest_rank)).all()
    # Provider quote time lives in data; a row insertion time must never replace it.
    return [OptionOut.model_validate({**row.data, "id": row.id, "fairest_rank": row.fairest_rank}) for row in rows]


@router.get("/trips/{trip_id}/options/status", response_model=GenerationOut)
def generation_status(trip_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    require_trip_member(session, trip_id, user)
    return public_status(session.get(OptionGeneration, trip_id))


def _worker(trip_id: str, run_id: str):
    with Session(engine) as session:
        trip = session.get(Trip, trip_id)
        if trip is None:
            return None
        chat_id = trip.chat_id
        try:
            published = generate_options(session, trip, run_id=run_id)
        except Exception as exc:
            from app.integrations.serpapi_client import TravelDataError
            unavailable = isinstance(exc, TravelDataError) and exc.code == 'provider_not_configured'
            session.rollback()
            # No exception repr/traceback: model or HTTP errors may contain private input or credentials.
            finish_state(session, trip_id, run_id, "failed", {"message": "Recommendations are unavailable until the provider is connected." if unavailable else "Option generation failed. Please retry."})
            return None
        return chat_id if published else None


async def _background(trip_id: str, run_id: str):
    chat_id = await run_in_threadpool(_worker, trip_id, run_id)
    if chat_id:
        await hub.to_chat(chat_id, {"type": "options.ready", "tripId": trip_id})
        await hub.to_chat(chat_id, {"type": "trip.stage", "tripId": trip_id, "stage": "options"})


@router.post("/trips/{trip_id}/options/generate", response_model=GenerationOut, status_code=202)
def generate(trip_id: str, background: BackgroundTasks, body: GenerateIn | None = None,
             user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    trip = require_trip_member(session, trip_id, user)
    from app.models import PlannerSession
    planner = session.get(PlannerSession, trip_id)
    if planner:
        raise HTTPException(409, "Use the approved planner recommendation endpoint.")
    if trip.stage not in {"checkin", "options"}:
        raise HTTPException(409, "Options can be generated during check-in or options review.")
    run, started = start_run(session, trip, body.inputs if body else None)
    result = public_status(run)
    if started:
        background.add_task(_background, trip_id, run.run_id)
    return result
