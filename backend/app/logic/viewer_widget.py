"""Owner-scoped flight widget evidence. No private ceilings or another viewer's data leave this service."""
import hashlib
from datetime import datetime
from sqlmodel import select, delete
from app.models import WidgetItinerary, Trip, PlannerSession, OptionGeneration
from app.logic.generation import revision, recent
from app.logic.widget_evidence import public_url
from app.integrations.serpapi_client import SerpApiClient
from app.schemas import WidgetSpecial


def publish_itineraries(session,trip_id,candidates,options,inputs):
    chosen={option.id for option in options}
    session.exec(delete(WidgetItinerary).where(WidgetItinerary.trip_id==trip_id))
    for candidate in candidates:
        option_id='opt-'+hashlib.sha256(f'{trip_id}:{candidate.id}'.encode()).hexdigest()[:24]
        if option_id not in chosen:
            continue
        for person in candidate.participants:
            flight=person.flight
            if not flight or not flight.complete or not flight.booking_token or not flight.retrieved_at:
                continue
            session.merge(WidgetItinerary(option_id=option_id,user_id=person.user_id,trip_id=trip_id,data={
                'origin':person.origin_airport,'destination':flight.destination_id,
                'booking_token':flight.booking_token,'outbound':inputs.checkin.isoformat(),
                'inbound':inputs.checkout.isoformat(),'retrieved_at':flight.retrieved_at.isoformat(),
                'image':public_url(candidate.lodging_image_url),'image_alt':candidate.lodging_name,
                'cost':float(person.flight_cost) if person.flight_cost is not None else None,'currency':person.currency,
            }))


def booking_url(payload):
    for option in payload.get('booking_options',[]) if isinstance(payload.get('booking_options'),list) else []:
        if not isinstance(option,dict):
            continue
        together=option.get('together') or option
        if not isinstance(together,dict):
            continue
        request=together.get('booking_request') or {}
        if isinstance(request,dict) and not request.get('post_data') and public_url(request.get('url')):
            return public_url(request['url'])
        if public_url(together.get('link')):
            return public_url(together['link'])
    return None


def flight_widget(session,trip_id,user_id,option_id,location_granted,client=None):
    if not location_granted:
        return None
    trip=session.get(Trip,trip_id)
    planner=session.get(PlannerSession,trip_id)
    run=session.get(OptionGeneration,trip_id)
    if not planner or planner.status not in {'approved','picked'} or not run or recent(run) or run.published_revision!=revision(session,trip):
        return None
    evidence=session.get(WidgetItinerary,(option_id,user_id))
    if not evidence or evidence.trip_id!=trip_id:
        return None
    data=evidence.data.copy()
    if not public_url(data.get('image')) or not data.get('destination'):
        return None
    fingerprint=run.published_revision
    session.rollback()
    try:
        raw=(client or SerpApiClient()).search({'engine':'google_flights','departure_id':data['origin'],
            'arrival_id':data['destination'],'outbound_date':data['outbound'],'return_date':data['inbound'],
            'booking_token':data['booking_token'],'type':1,'adults':1,'currency':data['currency'],'hl':'en'})
        link=booking_url(raw)
        if not link:
            return None
    except Exception:
        return None
    session.expire_all()
    run=session.get(OptionGeneration,trip_id)
    trip=session.get(Trip,trip_id)
    planner=session.get(PlannerSession,trip_id)
    if not run or run.published_revision!=fingerprint or revision(session,trip)!=fingerprint or recent(run) or planner.status not in {'approved','picked'}:
        return None
    return WidgetSpecial(id=option_id+'-flight',kind='flight',for_viewer_id=user_id,
        origin_code=data['origin'],destination_code=data['destination'],
        image={'src':data['image'],'alt':data['image_alt']},title=f"{data['origin']} → {data['destination']}",
        subtitle='Your round-trip flight',date_label=f"{data['outbound']} – {data['inbound']}",
        booking={'label':'View flight','url':link},choices=[],provider='SerpApi Google Flights',
        retrieved_at=datetime.fromisoformat(data['retrieved_at']))
