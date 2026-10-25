"""Persisted public planner state, optimistic edits and revision-scoped approvals."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from math import ceil
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import update
from sqlmodel import Session, select

from app.config import get_settings
from app.logic.listening import (new_template, effective_attendance, attending, missing_fields,
                                 semantic_signature, public_text, safe_updates)
from app.logic.generation import public_status, recent
from app.models import (Trip, PlannerSession, PlannerApproval, ListeningBatch, Message,
                        OptionGeneration, TripOption, VenueRecommendation)
from app.privacy.access import member_ids
from app.schemas import PlannerOut, OptionOut, VenueOut


def now():
    return datetime.now(UTC)


def age(value):
    return now() - value.replace(tzinfo=UTC)


def active(session, chat_id):
    return session.exec(select(PlannerSession).join(Trip).where(Trip.chat_id == chat_id)
                        .order_by(PlannerSession.created_at.desc())).first()


def create(session, chat_id, user_id, body):
    try:
        ZoneInfo(body.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Choose a valid timezone.") from None
    trip = Trip(chat_id=chat_id, created_by=user_id)
    session.add(trip)
    session.flush()
    template = new_template(body.title, body.topic, body.location, initiator=user_id,
                            members=tuple(sorted(member_ids(session, chat_id))))
    if public_text(body.title + body.location) != body.title + body.location:
        raise HTTPException(422, "Keep financial details in your private check-in.")
    planner = PlannerSession(trip_id=trip.id, title=template['title'], topic=body.topic,
                             timezone=body.timezone, template=template)
    session.add(planner)
    session.commit()
    return planner


def require_planner(session, trip_id):
    planner = session.get(PlannerSession, trip_id)
    if planner is None:
        raise HTTPException(404, "Planner not found.")
    return planner


def speaker(session, chat_id, user, demo_id=None):
    if not demo_id or demo_id == user.id:
        return user.id
    from app.demo import DEMO_CHAT_ID, DEMO_USER_ID
    settings = get_settings()
    if (not settings.demo_mode or settings.app_env != 'dev' or user.id != DEMO_USER_ID
            or chat_id != DEMO_CHAT_ID or demo_id not in member_ids(session, chat_id)):
        raise HTTPException(403, "Public demo perspective is unavailable.")
    return demo_id


def save(session, planner, template=None, *, internal=None, **values):
    # Every mutation takes the parent lock first, matching publication and picking.
    session.exec(select(Trip).where(Trip.id == planner.trip_id).with_for_update()).one()
    old_revision = planner.revision
    values.update(revision=old_revision + 1, updated_at=now())
    if template is not None:
        values['template'] = template
        values['title'] = template['title']
        if semantic_signature(template) != semantic_signature(planner.template):
            values['approval_revision'] = planner.approval_revision + 1
    if internal is not None:
        values['internal'] = internal
    changed = session.execute(update(PlannerSession).where(PlannerSession.trip_id == planner.trip_id,
                  PlannerSession.revision == old_revision).values(**values))
    if changed.rowcount != 1:
        session.rollback()
        raise HTTPException(409, "The plan changed. Refresh and try again.")
    session.flush()
    session.expire(planner)
    return planner


def synchronize_members(session, planner):
    trip = session.get(Trip,planner.trip_id)
    ids = sorted(member_ids(session,trip.chat_id))
    if ids == planner.template['members'] or planner.status == 'picked':
        return planner
    template = deepcopy(planner.template)
    template['members'] = ids
    save(session,planner,template,status='collecting',epoch=planner.epoch+1,approved_members=[])
    trip.stage = 'collecting'
    trip.picked_option_id = None
    session.add(trip)
    session.commit()
    return planner


def snapshot(session, planner):
    synchronize_members(session,planner)
    trip = session.get(Trip, planner.trip_id)
    batches = session.exec(select(ListeningBatch).where(ListeningBatch.trip_id == trip.id,
                              ListeningBatch.epoch == planner.epoch)).all()
    statuses = {b.status for b in batches}
    listening = ('listening' if 'processing' in statuses else 'queued' if 'queued' in statuses
                 else 'failed' if 'failed' in statuses else 'idle')
    missing = missing_fields(planner.template)
    eligible = sorted(attending(planner.template) & set(member_ids(session, trip.chat_id)))
    votes = session.exec(select(PlannerApproval).where(PlannerApproval.trip_id == trip.id,
                         PlannerApproval.revision == planner.approval_revision)).all()
    run = session.get(OptionGeneration, trip.id)
    generation = public_status(run)
    from app.logic.generation import revision
    valid_results = (planner.status in {'approved', 'picked'} and run is not None
                     and run.published_revision == revision(session,trip))
    # Travel publication stores its binding in the opaque generation fingerprint instead.
    if planner.topic == 'Travel' and planner.status in {'approved', 'picked'} and run and run.status == 'ready':
        from app.logic.generation import revision
        valid_results = run.published_revision == revision(session, trip)
    if planner.topic == 'Travel':
        options = session.exec(select(TripOption).where(TripOption.trip_id == trip.id)).all() if valid_results else []
        recommendations = {'kind': 'travel', 'options': [OptionOut.model_validate(r.data) for r in options]}
    else:
        rows = session.exec(select(VenueRecommendation).where(VenueRecommendation.trip_id == trip.id,
                            VenueRecommendation.revision == planner.approval_revision)).all() if valid_results else []
        recommendations = {'kind': 'venues', 'venues': [VenueOut.model_validate(r.data) for r in rows]}
    return PlannerOut(trip_id=trip.id, title=planner.title, topic=planner.topic, timezone=planner.timezone,
        revision=planner.revision, approval_revision=planner.approval_revision, status=planner.status,
        template=planner.template, attendance=effective_attendance(planner.template),
        poll={'eligible': eligible, 'approvals': sorted(v.user_id for v in votes if v.approve and v.user_id in eligible),
              'changes': sorted(v.user_id for v in votes if not v.approve and v.user_id in eligible),
              'required': max(1, ceil(planner.threshold * len(eligible))), 'threshold': planner.threshold,
              'ready': not missing and listening == 'idle' and bool(eligible)},
        listening=listening, missing=missing, generation=generation, recommendations=recommendations,
        provenance={m.id:m.sender_id for m in session.exec(select(Message).where(Message.chat_id==trip.chat_id,
            Message.id.in_(list(planner.template.get('sources',{}).values())))).all()},
        priced_members=planner.approved_members, picked_id=trip.picked_option_id)


def edit(session, planner, body, actor):
    if planner.status != 'collecting':
        raise HTTPException(409, "Revise the plan before changing its criteria.")
    if body.revision != planner.revision:
        raise HTTPException(409, "The plan changed. Refresh and try again.")
    template, internal = deepcopy(planner.template), deepcopy(planner.internal)
    if body.field == 'threshold':
        if body.value not in (.4, .5, .6):
            raise HTTPException(422, "Choose 40%, 50%, or 60%.")
        save(session, planner, threshold=body.value,
             approval_revision=planner.approval_revision + (body.value != planner.threshold))
    else:
        if body.field == 'where.origins':
            if not isinstance(body.value, str) or not 1 <= len(body.value.strip()) <= 120 or any(c.isdigit() for c in body.value):
                raise HTTPException(422, "Supply a coarse city or confirmed airport.")
            template['where']['origins'][actor] = body.value.strip()
        else:
            updates = [{'field': body.field, 'value': body.value, 'user_id': actor if body.field in
                        {'attendance','preferences','hard_constraints','when.flexibility'} else None,
                        'source_message_id': 'manual'}]
            template, decisions = safe_updates(template, updates, [{'id':'manual', 'user_id':actor}])
            if not decisions or not all(d['accepted'] for d in decisions):
                raise HTTPException(422, "That value is not valid for this field.")
        key = f"{body.field}:{actor if body.field in {'attendance','preferences','hard_constraints','when.flexibility','where.origins'} else 'group'}"
        internal.setdefault('field_versions', {})[key] = planner.revision + 1
        template['sources'][key] = 'manual'
        save(session, planner, template, internal=internal)
    session.commit()
    return planner


def enqueue(session, planner, message):
    synchronize_members(session,planner)
    if planner.status != 'collecting':
        return
    template = deepcopy(planner.template)
    if message.sender_id not in template['spoke']:
        template['spoke'].append(message.sender_id)
    save(session, planner, template)
    session.add(ListeningBatch(trip_id=planner.trip_id, epoch=planner.epoch,
                message_ids=[message.id], source_revisions={message.id:planner.revision}))
    session.commit()


def claim_batch(session):
    # Recover interrupted leases. Obsolete epochs are ignored and cannot apply results.
    rows = session.exec(select(ListeningBatch).where(ListeningBatch.status.in_(['queued','processing']))
                        .order_by(ListeningBatch.queued_at)).all()
    for row in rows:
        if row.status == 'processing' and row.started_at and age(row.started_at) > timedelta(seconds=90):
            row.status = 'queued'
            row.lease_id = None
            session.add(row)
    session.commit()
    for row in rows:
        planner = session.get(PlannerSession, row.trip_id)
        if not planner or planner.status != 'collecting' or row.epoch != planner.epoch or row.status != 'queued':
            continue
        same = [b for b in rows if b.trip_id == row.trip_id and b.epoch == planner.epoch]
        if any(b.status == 'processing' for b in same):
            continue
        queued = [b for b in same if b.status == 'queued']
        if len(queued) < 6 and age(queued[-1].queued_at).total_seconds() < get_settings().listener_debounce_seconds:
            continue
        selected = []
        size = 0
        for queued_batch in queued:
            if size + len(queued_batch.message_ids) > 6:
                break
            selected.append(queued_batch)
            size += len(queued_batch.message_ids)
        ids = [mid for b in selected for mid in b.message_ids][:6]
        revisions = {mid:rev for b in selected for mid, rev in b.source_revisions.items() if mid in ids}
        lease = uuid4().hex
        changed = session.execute(update(ListeningBatch).where(ListeningBatch.id == row.id,
                   ListeningBatch.status == 'queued').values(status='processing', lease_id=lease,
                   started_at=now(), message_ids=ids, source_revisions=revisions))
        if changed.rowcount != 1:
            session.rollback()
            continue
        for other in selected[1:]:
            session.delete(other)
        session.commit()
        return row.id, lease
    return None


def listener_context(session, planner, batch):
    from app.privacy.context import GroupContext, GroupMember
    from app.models import User
    trip = session.get(Trip, planner.trip_id)
    messages = session.exec(select(Message).where(Message.chat_id == trip.chat_id).order_by(Message.sent_at, Message.id)).all()
    indices = [i for i,m in enumerate(messages) if m.id in batch.message_ids]
    current = [{'id':m.id,'user_id':m.sender_id,'text':public_text(m.body)} for m in messages if m.id in batch.message_ids]
    def context_messages(items):
        return [{'id':m.id,'user_id':m.sender_id,'text':public_text(m.body)} for m in items]
    template = deepcopy(planner.template)
    template['where'].pop('origins', None)
    template.pop('base_location', None)
    template.pop('sources', None)
    users = session.exec(select(User).where(User.id.in_(template['members']))).all()
    listener = {'template':template, 'batch':current,
        'before':context_messages(messages[max(0,min(indices)-4):min(indices)]) if indices else [],
        'after':context_messages(messages[max(indices)+1:max(indices)+3]) if indices else [],
        'today':datetime.now(ZoneInfo(planner.timezone)).date().isoformat(), 'timezone':planner.timezone,
        'notes':public_text(planner.internal.get('notes',''))[:3000]}
    return GroupContext(trip_id=trip.id, members=tuple(GroupMember(id=u.id,name=u.display_name) for u in users),
                        recent_messages=(), facts=(), listener=listener), current


def process_batch(engine, batch_id, lease):
    from app.integrations import muse_group
    from app.logic.listening import CLUSTER_FIELDS
    with Session(engine) as session:
        batch = session.get(ListeningBatch, batch_id)
        planner = require_planner(session, batch.trip_id)
        ctx, messages = listener_context(session, planner, batch)
        epoch, trip_id, base_revision = planner.epoch, planner.trip_id, planner.revision
        signature = semantic_signature(ctx.listener['template'])
        should_predict = (any(not planner.template['cluster'].get(field) for field in CLUSTER_FIELDS[planner.topic])
                          and planner.internal.get('prediction_signature') != signature)
        session.rollback()  # no transaction across model I/O
        try:
            if not get_settings().muse_api_key:
                raise RuntimeError('unavailable')
            result = muse_group.listen_planner(ctx)
            if not isinstance(result, dict) or not isinstance(result.get('updates'), list):
                raise ValueError('invalid result')
            prediction = {}
            if should_predict:
                try:
                    prediction = muse_group.predict_planner(ctx).get('suggestions', {})
                except Exception:
                    pass  # optional prediction never blocks listening
        except Exception:
            session.execute(update(ListeningBatch).where(ListeningBatch.id == batch_id,
                ListeningBatch.lease_id == lease).values(status='failed'))
            session.commit()
            return trip_id
        session.expire_all()
        batch = session.get(ListeningBatch, batch_id)
        session.exec(select(Trip).where(Trip.id == trip_id).with_for_update()).one()
        planner = session.exec(select(PlannerSession).where(PlannerSession.trip_id == trip_id).with_for_update()).one()
        if batch.lease_id != lease or batch.status != 'processing' or planner.epoch != epoch or planner.status != 'collecting':
            return trip_id
        internal = deepcopy(planner.internal)
        template, _ = safe_updates(planner.template, result['updates'], messages,
                  field_versions=internal.get('field_versions'), source_revisions=batch.source_revisions)
        for field, value in prediction.items() if isinstance(prediction,dict) else []:
            if field in CLUSTER_FIELDS[planner.topic] and not template['cluster'].get(field):
                proposed, decisions = safe_updates(template, [{'field':field,'value':value,'source_message_id':'suggestion'}],
                                                 [{'id':'suggestion','user_id':None}],
                                                 field_versions=internal.get('field_versions'),
                                                 source_revisions={'suggestion':base_revision})
                if decisions and decisions[0]['accepted']:
                    template = proposed
                    template['sources'][f'{field}:group'] = 'suggested'
        internal['notes'] = public_text(str(result.get('notes','')))[:3000]
        internal['prediction_signature'] = signature
        save(session, planner, template, internal=internal)
        batch.status = 'done'
        session.add(batch)
        session.commit()
        return trip_id
