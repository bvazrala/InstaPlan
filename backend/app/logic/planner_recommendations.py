"""Public recommendation orchestration and private-safe venue evaluation."""
import hashlib
from datetime import UTC, datetime
from urllib.parse import quote
from sqlmodel import Session, select, delete
from sqlalchemy import update
from app.models import PlannerSession, Trip, OptionGeneration, VenueRecommendation, PrivatePrefs
from app.logic.generation import finish_state, recent, revision, utcnow
from app.logic.planning import PlanningInput, Constraint, Preference
from app.schemas import VenueOut, PrivatePrefsData
from app.privacy.crypto import decrypt_json
from app.integrations.serpapi_client import SerpApiClient
from app.integrations.serpapi_normalized import Place, _parse_created_at
from app.logic.widget_evidence import public_url, requested_special, event_for_venue


def travel_inputs(planner):
    raw = planner.internal.get('pricing',{})
    inputs = PlanningInput.model_validate(raw)
    if planner.internal.get('simple_flow') and not raw:
        import re
        from datetime import date
        from app.logic.planning import Destination
        inputs.origins={uid:code for uid,code in planner.template['where']['origins'].items()
                        if uid in planner.approved_members and re.fullmatch(r'[A-Z]{3}',code)}
        location=planner.template['where']['search_area'] or ''
        if re.fullmatch(r'[A-Z]{3}',location):
            inputs.destinations=[Destination(name=location,airports=[location])]
        labels=[str((planner.template['when'].get('agreed') or {}).get('label',''))]
        labels += [window['label'] for windows in planner.template['when']['flexibility'].values() if windows for window in windows]
        for label in labels:
            dates=list(dict.fromkeys(re.findall(r'\b\d{4}-\d{2}-\d{2}\b',label)))
            if len(dates)==2:
                try: inputs.checkin,inputs.checkout=map(date.fromisoformat,dates)
                except ValueError: pass
                break
    # Public natural-language hard requirements remain unverified rather than disappearing.
    import re
    inputs.constraints = []
    for uid, rules in planner.template['hard_constraints'].items():
        if uid not in planner.approved_members:
            continue
        for text in rules:
            value = text.strip().casefold()
            if value in {'flight only','flights only','only flights','must fly'}:
                rule = Constraint(kind='flight_only',member_id=uid)
            elif value in {'nonstop','non-stop','direct flights','no stops'}:
                rule = Constraint(kind='max_stops',member_id=uid,limit=0)
            elif match := re.fullmatch(r'(?:max|maximum|at most) (\d+) stops?',value):
                rule = Constraint(kind='max_stops',member_id=uid,limit=int(match[1]))
            elif match := re.fullmatch(r'(?:max|maximum|at most) (\d+) hours?(?: round trip)?',value):
                rule = Constraint(kind='max_duration',member_id=uid,limit=int(match[1])*60)
            else:
                rule = Constraint(kind='unsupported',member_id=uid)
            inputs.constraints.append(rule)
    transport = planner.template['cluster'].get('trip_type')
    lodging = planner.template['cluster'].get('accommodation')
    if transport and transport != 'flight' or lodging == 'none':
        inputs.constraints.append(Constraint(kind='unsupported'))
    inputs.preferences = [Preference(member_id=uid,category='Destination',value=value,score=1)
        for uid, values in planner.template['preferences'].items() if uid in planner.approved_members for value in values]
    return inputs


def place_fallback(planner):
    return bool(planner and planner.topic=='Travel' and planner.internal.get('simple_flow') and (
        planner.template['cluster'].get('trip_type')!='flight' or
        travel_inputs(planner).missing(planner.approved_members)))


def venue_constraints_verified(session, planner):
    if any(values for uid,values in planner.template['hard_constraints'].items() if uid in planner.approved_members):
        return False
    if planner.internal.get('simple_flow'):
        return True
    for row in session.exec(select(PrivatePrefs).where(PrivatePrefs.trip_id == planner.trip_id)):
        if row.user_id not in planner.approved_members:
            continue
        try:
            prefs = PrivatePrefsData.model_validate(decrypt_json(row.data_encrypted))
        except Exception:
            return False
        if prefs.dietary or prefs.accessibility or prefs.no_gos:
            return False
    return True


def generate_venues(session, trip, planner, run_id, client=None):
    run = session.get(OptionGeneration, trip.id)
    if not run or run.run_id != run_id or not recent(run) or planner.status != 'approved':
        return False
    if not planner.approved_members:
        finish_state(session,trip.id,run_id,'needs_input',{'message':'At least one going member is needed. Revise attendance.'})
        return False
    template = planner.template
    selected = template['where']['destination']
    exact = selected if selected and selected.get('kind','venue') == 'venue' else None
    location = selected['name'] if selected else template['where']['search_area'] or template.get('base_location')
    if not location:
        finish_state(session, trip.id, run_id, 'needs_input', {'message':'Choose a city or place before searching.', 'missing':['location']})
        return False
    cluster = template['cluster']
    query = (' '.join(cluster.get('cuisine',[]))+' restaurants '+str(cluster.get('meal_type',''))) if planner.topic == 'Dining' else cluster.get('activity_type','things to do')
    if planner.topic=='Travel':
        query = 'hotels and stays'
    public_preferences = {uid:template['preferences'].get(uid,[]) for uid in planner.approved_members}
    terms = list(dict.fromkeys(value for values in public_preferences.values() for value in values))[:4]
    if terms:
        query += ' ' + ' '.join(terms)[:300]
    client = client or SerpApiClient()
    params = {'engine':'google_maps','type':'search','q':f'{query} in {location}','hl':'en'}
    if exact:
        params = {'engine':'google_maps','type':'place','place_id':exact['id'],'hl':'en'}
    session.rollback()
    payload = client.search(params)
    rows = [payload['place_results']] if exact and isinstance(payload.get('place_results'),dict) else payload.get('local_results',[]) if not exact else []
    if not isinstance(rows,list):
        raise ValueError('malformed venues')
    retrieved_at = _parse_created_at(payload) or datetime.now(UTC)
    event_rows = []
    event_time = retrieved_at
    event_kind = requested_special(cluster.get('activity_type')) if planner.topic=='Entertainment' else None
    if event_kind:
        try:
            target = ' '.join(filter(None,[exact['name'],exact.get('address')])) if exact else location
            event_payload = client.search({'engine':'google_events','q':f"{cluster.get('activity_type')} {target}",'hl':'en'})
            event_rows = event_payload.get('events_results',[])
            event_time = _parse_created_at(event_payload) or datetime.now(UTC)
        except Exception:
            pass  # The venue remains useful when the optional ticket feed is unavailable.
    session.expire_all()
    trip = session.exec(select(Trip).where(Trip.id == trip.id).with_for_update()).one()
    planner = session.get(PlannerSession,trip.id)
    run = session.get(OptionGeneration,trip.id)
    if run.run_id != run_id or not recent(run) or planner.status != 'approved' or revision(session,trip) != run.revision:
        finish_state(session,trip.id,run_id,'failed',{'message':'The plan changed. Approve the new revision before searching.'})
        return False
    verified = venue_constraints_verified(session,planner)
    venues = {}
    for row in rows[:30]:
        if not isinstance(row,dict):
            continue
        place = Place.from_dict(row)
        identity = place.place_id or place.data_id or f'{place.title}:{place.address}'
        if exact and place.place_id != exact['id']:
            continue
        if not place.title or identity in venues:
            continue
        venue_id = 'venue-'+hashlib.sha256(f'{trip.id}:{identity}'.encode()).hexdigest()[:24]
        url = place.website_url
        if not url and place.place_id:
            url = 'https://www.google.com/maps/search/?api=1&query='+quote(place.title)+'&query_place_id='+quote(place.place_id)
        if url and not url.startswith(('https://','http://')):
            url = None
        evidence = [f'Provider category: {place.category}'] if place.category else []
        provider_words = ' '.join([place.title or '',place.category or '',*place.types]).casefold()
        member_matches = [sum(value.casefold() in provider_words for value in values)/len(values)
                          for values in public_preferences.values() if values]
        # A missing provider match is unknown, not proof that a preference is violated.
        fit = round(100 * sum(member_matches)/len(member_matches),1) if member_matches and any(member_matches) else None
        if fit is not None:
            evidence.append('Some public preferences match provider-reported names or categories; other preferences remain unverified.')
        warnings = ['Exact cost unknown; price levels are not dollar quotes.',
                    'Opening hours for the planned time and ticket availability are unverified.',
                    'Dietary and accessibility suitability must be confirmed with the venue.']
        if not verified:
            warnings.append('Requirements still need verification before this venue can be picked.')
        venues[identity] = VenueOut(kind="restaurant" if planner.topic=="Dining" else "stay" if planner.topic=="Travel" else "venue",id=venue_id,title=place.title,address=place.address,rating=place.rating,
            price_level=place.price_level,url=url,retrieved_at=retrieved_at,evidence=evidence,
            image_url=public_url(place.image_url),review_count=place.review_count,category=place.category,
            special=event_for_venue(event_rows,place.title,event_kind,retrieved_at=event_time,venue_address=place.address,
                exact_date=(template['when'].get('agreed') or {}).get('date')),
            warnings=warnings,pick_eligible=verified,fit=fit)
    results = sorted(venues.values(),key=lambda v:(not bool(v.special),v.fit is None,-(v.fit or 0),v.rating is None,-(v.rating or 0),v.id))[:6]
    changed = session.execute(update(OptionGeneration).where(OptionGeneration.trip_id==trip.id,
        OptionGeneration.run_id==run_id,OptionGeneration.status.in_(['resolving','generating'])).values(
        status='ready',published_revision=run.revision,updated_at=utcnow(),result={
        'planner_revision':planner.approval_revision,'option_count':len(results),'recommendation_kind':'venues'}))
    if changed.rowcount != 1:
        session.rollback()
        return False
    session.exec(delete(VenueRecommendation).where(VenueRecommendation.trip_id==trip.id))
    for rank,venue in enumerate(results,1):
        venue.recommendation_rank=rank
        session.add(VenueRecommendation(id=venue.id,trip_id=trip.id,revision=planner.approval_revision,
                                        data=venue.model_dump(mode='json')))
    trip.stage='options'
    session.add(trip)
    session.commit()
    return True
