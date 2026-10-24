"""Trip session (group-visible): start, trip card facts, vote, stage changes, pick."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, func, select

from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.logic.trip_state import InvalidTransition, Stage, advance, has_majority
from app.models import Fact, PrivatePrefs, Trip, TripOption, TripVote
from app.privacy.access import member_ids, require_chat_member, require_trip_member
from app.realtime import hub
from app.schemas import ApiModel, FactOut, FactPatch, PickIn, TripOut, VoteIn

router = APIRouter(tags=["trips"])


class StageIn(ApiModel):
    stage: Stage


def trip_out(session: Session, trip: Trip) -> TripOut:
    count = lambda model: session.exec(select(func.count()).select_from(model).where(model.trip_id == trip.id)).one()
    yes = session.exec(select(func.count()).select_from(TripVote).where(TripVote.trip_id == trip.id, TripVote.going)).one()
    return TripOut(id=trip.id, chat_id=trip.chat_id, stage=trip.stage, picked_option_id=trip.picked_option_id,
                   yes_votes=yes, member_count=len(member_ids(session, trip.chat_id)), checkins_done=count(PrivatePrefs))


async def _set_stage(session: Session, trip: Trip, target: Stage) -> TripOut:
    try:
        trip.stage = advance(trip.stage, target)
    except InvalidTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    session.add(trip)
    session.commit()
    await hub.to_chat(trip.chat_id, {"type": "trip.stage", "tripId": trip.id, "stage": trip.stage})
    # TODO(R22): on CHECKIN, start each member's private check-in (routers/checkins.start_checkin).
    return trip_out(session, trip)


@router.post("/chats/{chat_id}/trips", response_model=TripOut, status_code=201)
async def start_trip(chat_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    """R1: someone taps "Plan a trip". Starts listening to the chat for trip facts."""
    require_chat_member(session, chat_id, user)
    trip = Trip(chat_id=chat_id, created_by=user.id)
    session.add(trip)
    session.commit()
    await hub.to_chat(chat_id, {"type": "trip.stage", "tripId": trip.id, "stage": trip.stage})
    return trip_out(session, trip)


@router.get("/trips/{trip_id}", response_model=TripOut)
def get_trip(trip_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    return trip_out(session, require_trip_member(session, trip_id, user))


@router.post("/trips/{trip_id}/stage", response_model=TripOut)
async def change_stage(trip_id: str, body: StageIn, user: CurrentUser = Depends(get_current_user),
                       session: Session = Depends(get_session)):
    """Call the vote, go back to collecting, move on to settle up. Allowed moves: logic/trip_state.py."""
    return await _set_stage(session, require_trip_member(session, trip_id, user), body.stage)


@router.get("/trips/{trip_id}/facts", response_model=list[FactOut])
def list_facts(trip_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    require_trip_member(session, trip_id, user)
    return session.exec(select(Fact).where(Fact.trip_id == trip_id)).all()


@router.patch("/trips/{trip_id}/facts/{fact_id}", response_model=FactOut)
def edit_fact(trip_id: str, fact_id: str, body: FactPatch, user: CurrentUser = Depends(get_current_user),
              session: Session = Depends(get_session)):
    """R5: anyone in the group can correct a fact."""
    require_trip_member(session, trip_id, user)
    fact = session.get(Fact, fact_id)
    if fact is None or fact.trip_id != trip_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    fact.value = body.value
    session.add(fact)
    session.commit()
    return fact


@router.delete("/trips/{trip_id}/facts/{fact_id}", status_code=204)
def delete_fact(trip_id: str, fact_id: str, user: CurrentUser = Depends(get_current_user),
                session: Session = Depends(get_session)):
    require_trip_member(session, trip_id, user)
    fact = session.get(Fact, fact_id)
    if fact is not None and fact.trip_id == trip_id:
        session.delete(fact)
        session.commit()
    return Response(status_code=204)


@router.post("/trips/{trip_id}/vote", response_model=TripOut)
async def vote(trip_id: str, body: VoteIn, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    """R8: majority yes locks the trip and starts private check-ins."""
    trip = require_trip_member(session, trip_id, user)
    if trip.stage != Stage.VOTING:
        raise HTTPException(status.HTTP_409_CONFLICT, "No vote is open")
    session.merge(TripVote(trip_id=trip_id, user_id=user.id, going=body.going))
    session.commit()
    out = trip_out(session, trip)
    if has_majority(out.yes_votes, out.member_count):
        return await _set_stage(session, trip, Stage.CHECKIN)
    await hub.to_chat(trip.chat_id, {"type": "trip.stage", "tripId": trip.id, "stage": trip.stage})
    return out


@router.post("/trips/{trip_id}/pick", response_model=TripOut)
async def pick_option(trip_id: str, body: PickIn, user: CurrentUser = Depends(get_current_user),
                      session: Session = Depends(get_session)):
    """R15: the group picks an option."""
    trip = require_trip_member(session, trip_id, user)
    option = session.get(TripOption, body.option_id)
    if option is None or option.trip_id != trip_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    trip.picked_option_id = option.id
    return await _set_stage(session, trip, Stage.PICKED)
