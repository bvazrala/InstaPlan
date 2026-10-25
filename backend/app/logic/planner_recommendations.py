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
from app.integrations.serpapi_normalized import Place


def travel_inputs(planner):
    raw = planner.internal.get('pricing',{})
    inputs = PlanningInput.model_validate(raw)
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


def venue_constraints_verified(session, planner):
    if any(values for uid,values in planner.template['hard_constraints'].items() if uid in planner.approved_members):
        return False
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
    cluster = template['cluster']
    query = (' '.join(cluster.get('cuisine',[]))+' restaurants '+str(cluster.get('meal_type',''))) if planner.topic == 'Dining' else cluster.get('activity_type','things to do')
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
        venues[identity] = VenueOut(id=venue_id,title=place.title,address=place.address,rating=place.rating,
            price_level=place.price_level,url=url,retrieved_at=datetime.now(UTC),evidence=evidence,
            warnings=warnings,pick_eligible=verified,fit=fit)
    results = sorted(venues.values(),key=lambda v:(v.fit is None,-(v.fit or 0),v.rating is None,-(v.rating or 0),v.id))[:6]
    changed = session.execute(update(OptionGeneration).where(OptionGeneration.trip_id==trip.id,
        OptionGeneration.run_id==run_id,OptionGeneration.status.in_(['resolving','generating'])).values(
        status='ready',published_revision=run.revision,updated_at=utcnow(),result={
        'planner_revision':planner.approval_revision,'option_count':len(results)}))
    if changed.rowcount != 1:
        session.rollback()
        return False
    session.exec(delete(VenueRecommendation).where(VenueRecommendation.trip_id==trip.id))
    for venue in results:
        session.add(VenueRecommendation(id=venue.id,trip_id=trip.id,revision=planner.approval_revision,
                                        data=venue.model_dump(mode='json')))
    trip.stage='options'
    session.add(trip)
    session.commit()
    return True
