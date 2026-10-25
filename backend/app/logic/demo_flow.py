"""The demo's public RSVP poll and reset. Historical/private records are never repurposed."""
from copy import deepcopy
from datetime import UTC
from uuid import uuid4
from fastapi import HTTPException
from sqlmodel import select
from app.models import (Chat, DemoChatState, Trip, PlannerSession, PlannerApproval, ListeningBatch, OptionGeneration)
from app.logic import planner_service as service
from app.logic.listening import effective_attendance, missing_fields
from app.privacy.access import member_ids


def respond(session,trip,planner,actor,going,revision):
    session.exec(select(Trip).where(Trip.id==trip.id).with_for_update()).one()
    session.refresh(planner)
    if planner.status!='collecting' or revision!=planner.approval_revision:
        raise HTTPException(409,'This plan is no longer taking responses. Refresh it first.')
    before=service.snapshot(session,planner)
    if not before.poll.ready:
        raise HTTPException(409,'The poll opens once at least half the group has joined the conversation.')
    template=deepcopy(planner.template)
    template['attendance'][actor]={'status':'going' if going else 'not_going','condition':None}
    template['sources'][f'attendance:{actor}']='manual'
    if going and not template['when'].get('agreed') and actor not in template['when']['flexibility']:
        template['when']['flexibility'][actor]=[{'label':'Accepted the proposed timing'}]
        template['sources'][f'when.flexibility:{actor}']='manual'
    if not going:
        template['when']['flexibility'].pop(actor,None)
    # Responding to this proposal accumulates its ballots. Later conversational/manual criteria changes still reset them.
    service.save(session,planner,template,approval_revision=planner.approval_revision)
    session.merge(PlannerApproval(trip_id=trip.id,revision=planner.approval_revision,user_id=actor,approve=going))
    session.flush()
    poll=service.snapshot(session,planner).poll
    if poll.ready and len(poll.approvals)>=poll.required:
        roster=sorted(uid for uid,item in effective_attendance(planner.template).items()
                      if item['status']=='going' and uid in member_ids(session,trip.chat_id))
        service.save(session,planner,status='approved',approved_members=roster)
        trip.stage='confirmed'
        session.add(trip)
    session.commit()
    return planner


def reset_demo(session,chat_id,user):
    from app.config import get_settings
    from app.demo import DEMO_CHAT_ID,DEMO_USER_ID
    settings=get_settings()
    if not settings.demo_mode or settings.app_env!='dev' or chat_id!=DEMO_CHAT_ID or user.id!=DEMO_USER_ID:
        raise HTTPException(403,'Reset is available only in the local demo chat.')
    session.exec(select(Chat).where(Chat.id==chat_id).with_for_update()).one()
    cutoff=service.now()
    session.merge(DemoChatState(chat_id=chat_id,reset_at=cutoff))
    for planner in session.exec(select(PlannerSession).join(Trip).where(Trip.chat_id==chat_id)):
        service.save(session,planner,status='archived',epoch=planner.epoch+1,
                     approval_revision=planner.approval_revision+1)
        trip=session.get(Trip,planner.trip_id)
        trip.stage='settle'
        session.add(trip)
        for batch in session.exec(select(ListeningBatch).where(ListeningBatch.trip_id==planner.trip_id,
                    ListeningBatch.status.in_(['queued','processing','failed']))):
            batch.status='cancelled';batch.lease_id=None;session.add(batch)
        run=session.get(OptionGeneration,planner.trip_id)
        if run:
            run.run_id=uuid4().hex;run.status='failed';run.result={'message':'Demo reset.'};session.add(run)
    for trip in session.exec(select(Trip).where(Trip.chat_id==chat_id)):
        trip.stage='settle';session.add(trip)
        run=session.get(OptionGeneration,trip.id)
        if run and run.status in {'resolving','generating'}:
            run.run_id=uuid4().hex;run.status='failed';run.result={'message':'Demo reset.'};session.add(run)
    session.commit()
    return cutoff
