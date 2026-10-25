"""Unified planner API. All shared operations are authorized through current chat membership."""
from copy import deepcopy
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select
from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.logic import planner_service as service
from app.logic.generation import start_run, public_status, recent
from app.logic.listening import effective_attendance
from app.models import (Trip, PlannerSession, PlannerApproval, ListeningBatch, OptionGeneration,
                        VenueRecommendation, Chat)
from app.privacy.access import require_chat_member, require_trip_member, member_ids
from app.realtime import hub
from app.schemas import (PlannerCreate, PlannerEdit, PlannerVote, PlannerOut, PlacesQuery,
                         PlaceSelection, GenerateIn, PickIn, PlannerResponse, DemoResetOut)
from app.routers.options import _background

router = APIRouter(tags=['planner'])


async def changed(session, planner):
    trip = session.get(Trip,planner.trip_id)
    await hub.to_chat(trip.chat_id,{'type':'planner.updated','tripId':trip.id})
    return service.snapshot(session,planner)


def plan(session,trip_id,user):
    trip = require_trip_member(session,trip_id,user)
    planner = service.require_planner(session,trip_id)
    service.synchronize_members(session,planner)
    return trip,planner


def schedule(session,trip,planner,background):
    if planner.status != 'approved':
        raise HTTPException(409,'Approve the current plan before requesting recommendations.')
    run,started = start_run(session,trip)
    if started:
        background.add_task(_background,trip.id,run.run_id)
    return run


@router.post('/chats/{chat_id}/planners',response_model=PlannerOut,status_code=201)
async def create_planner(chat_id:str,body:PlannerCreate,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    require_chat_member(session,chat_id,user)
    session.exec(select(Chat).where(Chat.id==chat_id).with_for_update()).one()
    existing = service.active(session,chat_id)
    if existing and existing.status != 'picked':
        raise HTTPException(409,'This chat already has an active planner.')
    planner = service.create(session,chat_id,user.id,body)
    return await changed(session,planner)


@router.get('/chats/{chat_id}/planner',response_model=PlannerOut|None)
def active_planner(chat_id:str,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    require_chat_member(session,chat_id,user)
    planner = service.active(session,chat_id)
    return service.snapshot(session,planner) if planner else None


@router.get('/trips/{trip_id}/planner',response_model=PlannerOut)
def get_planner(trip_id:str,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    _,planner = plan(session,trip_id,user)
    return service.snapshot(session,planner)


@router.patch('/trips/{trip_id}/planner',response_model=PlannerOut)
async def edit_planner(trip_id:str,body:PlannerEdit,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    trip,planner = plan(session,trip_id,user)
    actor = service.speaker(session,trip.chat_id,user,body.demo_speaker_id)
    service.edit(session,planner,body,actor)
    return await changed(session,planner)


@router.post('/trips/{trip_id}/planner/approve',response_model=PlannerOut)
async def vote(trip_id:str,body:PlannerVote,background:BackgroundTasks,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    trip,planner = plan(session,trip_id,user)
    session.exec(select(Trip).where(Trip.id==trip_id).with_for_update()).one()
    session.refresh(planner)
    if planner.status != 'collecting' or body.revision != planner.approval_revision:
        raise HTTPException(409,'This approval revision is no longer open.')
    before = service.snapshot(session,planner)
    actor = service.speaker(session,trip.chat_id,user,body.demo_speaker_id)
    if actor not in before.poll.eligible:
        raise HTTPException(409,'Declined members do not vote on this plan.')
    if not before.poll.ready:
        raise HTTPException(409,'Wait for listening to finish and supply the missing details.')
    session.merge(PlannerApproval(trip_id=trip_id,revision=planner.approval_revision,user_id=actor,approve=body.approve))
    session.flush()
    after = service.snapshot(session,planner)
    values = {}
    if len(after.poll.approvals) >= after.poll.required:
        roster = sorted(uid for uid,entry in effective_attendance(planner.template).items()
                        if entry['status']=='going' and uid in member_ids(session,trip.chat_id))
        values = {'status':'approved','approved_members':roster}
        trip.stage='confirmed'
        session.add(trip)
    service.save(session,planner,**values)
    session.commit()
    if planner.status == 'approved':
        schedule(session,trip,planner,background)
    return await changed(session,planner)


@router.post('/trips/{trip_id}/planner/revise',response_model=PlannerOut)
async def revise(trip_id:str,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    trip,planner = plan(session,trip_id,user)
    service.save(session,planner,status='collecting',epoch=planner.epoch+1,
                 approval_revision=planner.approval_revision+1,approved_members=[])
    trip.stage='collecting'
    trip.picked_option_id=None
    session.add(trip)
    run=session.get(OptionGeneration,trip_id)
    if run and recent(run):
        run.status='failed'
        run.result={'message':'The plan was revised. Approve it again before searching.'}
        session.add(run)
    session.commit()
    return await changed(session,planner)


@router.post('/trips/{trip_id}/planner/retry',response_model=PlannerOut,status_code=202)
async def retry(trip_id:str,background:BackgroundTasks,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    trip,planner = plan(session,trip_id,user)
    if planner.status=='collecting':
        for batch in session.exec(select(ListeningBatch).where(ListeningBatch.trip_id==trip_id,
                ListeningBatch.epoch==planner.epoch,ListeningBatch.status=='failed')):
            batch.status='queued'
            batch.lease_id=None
            session.add(batch)
        session.commit()
    else:
        schedule(session,trip,planner,background)
    return await changed(session,planner)


@router.post('/trips/{trip_id}/planner/pricing',response_model=PlannerOut,status_code=202)
async def pricing(trip_id:str,body:GenerateIn,background:BackgroundTasks,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    trip,planner=plan(session,trip_id,user)
    if planner.status!='approved' or planner.topic!='Travel' or not body.inputs:
        raise HTTPException(409,'Approve a travel plan before confirming flight search details.')
    run=session.get(OptionGeneration,trip_id)
    if run and recent(run):
        raise HTTPException(409,'Wait for the current search to finish.')
    inputs=body.inputs
    expected = planner.template['where']['destination']
    label = expected['name'] if expected else planner.template['where']['search_area']
    if any(destination.name.casefold() != (label or '').casefold() for destination in inputs.destinations):
        raise HTTPException(422,'Keep the approved destination or revise the plan first.')
    agreed_date = (planner.template['when'].get('agreed') or {}).get('date')
    if agreed_date and inputs.checkin and inputs.checkin.isoformat() != agreed_date:
        raise HTTPException(422,'Keep the approved date or revise the plan first.')
    if set(inputs.origins)-set(planner.approved_members):
        raise HTTPException(422,'Only going members can have priced journeys.')
    # Public search corrections supply exact dates/airports without erasing frozen criteria.
    if inputs.constraints or inputs.preferences:
        raise HTTPException(422,'Edit preferences in the planner before approval.')
    internal=deepcopy(planner.internal)
    internal['pricing']=inputs.model_dump(mode='json')
    service.save(session,planner,internal=internal)
    session.commit()
    schedule(session,trip,planner,background)
    return await changed(session,planner)


@router.post('/trips/{trip_id}/planner/places')
def places(trip_id:str,body:PlacesQuery,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    plan(session,trip_id,user)
    from app.integrations.places import autocomplete, PlacesUnavailable
    try:
        return autocomplete(body.query,body.session_token)
    except PlacesUnavailable as exc:
        raise HTTPException(503,str(exc)) from None


@router.post('/trips/{trip_id}/planner/destination',response_model=PlannerOut)
async def destination(trip_id:str,body:PlaceSelection,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    _,planner=plan(session,trip_id,user)
    if planner.status!='collecting' or body.revision!=planner.revision:
        raise HTTPException(409,'Refresh or revise the plan before choosing a destination.')
    from app.integrations.places import details, PlacesUnavailable
    try:
        place=details(session,body.place_id,body.session_token)
    except PlacesUnavailable as exc:
        raise HTTPException(503,str(exc)) from None
    session.refresh(planner)
    if planner.status!='collecting' or body.revision!=planner.revision:
        raise HTTPException(409,'The plan changed during place lookup. Try again.')
    template=deepcopy(planner.template)
    template['where']['destination']=place
    template['sources']['where.destination:group']='manual'
    internal=deepcopy(planner.internal)
    internal.setdefault('field_versions',{})['where.destination:group']=planner.revision+1
    service.save(session,planner,template,internal=internal)
    session.commit()
    return await changed(session,planner)


@router.post('/trips/{trip_id}/planner/pick',response_model=PlannerOut)
async def pick(trip_id:str,body:PickIn,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    trip,planner=plan(session,trip_id,user)
    if planner.status!='approved':
        raise HTTPException(409,'The current revision must be approved before picking.')
    if planner.topic=='Travel':
        from app.routers.trips import pick_option
        await pick_option(trip_id,body,user,session)
        session.refresh(planner)
    else:
        trip=session.exec(select(Trip).where(Trip.id==trip_id).with_for_update()).one()
        from app.logic.generation import revision
        run=session.get(OptionGeneration,trip_id)
        if not run or recent(run) or run.published_revision!=revision(session,trip):
            raise HTTPException(409,'Wait for recommendations for the current approved revision.')
        row=session.get(VenueRecommendation,body.option_id)
        if not row or row.trip_id!=trip_id or row.revision!=planner.approval_revision:
            raise HTTPException(404,'Recommendation not found.')
        from app.logic.planner_recommendations import venue_constraints_verified
        if not row.data.get('pick_eligible') or not venue_constraints_verified(session,planner):
            raise HTTPException(409,'Requirements still need verification.')
        trip.picked_option_id=row.id
        trip.stage='picked'
        session.add(trip)
    if planner.status != 'picked':
        service.save(session,planner,status='picked')
    session.commit()
    return await changed(session,planner)


@router.post('/trips/{trip_id}/planner/respond',response_model=PlannerOut)
async def respond(trip_id:str,body:PlannerResponse,background:BackgroundTasks,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    trip,planner=plan(session,trip_id,user)
    from app.logic.demo_flow import respond as record_response
    actor=service.speaker(session,trip.chat_id,user,body.demo_speaker_id)
    record_response(session,trip,planner,actor,body.going,body.revision)
    if planner.status=='approved':
        schedule(session,trip,planner,background)
    return await changed(session,planner)


@router.post('/chats/{chat_id}/planner/places')
def creation_places(chat_id:str,body:PlacesQuery,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    require_chat_member(session,chat_id,user)
    from app.integrations.places import autocomplete,PlacesUnavailable
    try:
        return autocomplete(body.query,body.session_token)
    except PlacesUnavailable as exc:
        raise HTTPException(503,str(exc)) from None


@router.post('/chats/{chat_id}/demo/reset',response_model=DemoResetOut)
async def reset(chat_id:str,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    require_chat_member(session,chat_id,user)
    from app.logic.demo_flow import reset_demo
    cutoff=reset_demo(session,chat_id,user)
    await hub.to_chat(chat_id,{'type':'chat.reset','chatId':chat_id,'resetAt':cutoff.isoformat()})
    return DemoResetOut(reset_at=cutoff)
