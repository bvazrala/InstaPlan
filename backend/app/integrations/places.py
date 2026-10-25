"""Server-only Places picker. Exact destinations require a human selection."""
from urllib.parse import quote
import httpx
from app.config import get_settings
from app.integrations.cache import cached

class PlacesUnavailable(Exception):
    pass


def request(method, path, *, payload=None, params=None, field_mask, transport=None):
    key = get_settings().google_maps_api_key
    if not key:
        raise PlacesUnavailable('Places lookup is unavailable; enter a city manually.')
    try:
        with httpx.Client(timeout=15, transport=transport) as client:
            response = client.request(method, 'https://places.googleapis.com/v1/' + path,
                headers={'X-Goog-Api-Key':key, 'X-Goog-FieldMask':field_mask}, json=payload, params=params)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result,dict):
            raise ValueError()
        return result
    except (httpx.HTTPError, ValueError):
        raise PlacesUnavailable('Places lookup is unavailable; please retry or enter a city.') from None


def autocomplete(query, token):
    data = request('POST','places:autocomplete',payload={'input':query,'sessionToken':token},
        field_mask='suggestions.placePrediction.placeId,suggestions.placePrediction.text.text')
    return [{'id':p['placeId'],'label':p.get('text',{}).get('text','')} for entry in data.get('suggestions',[])[:6]
            if isinstance(p:=entry.get('placePrediction'),dict) and p.get('placeId')]


def details(session, place_id, token):
    def fetch():
        result = request('GET','places/'+quote(place_id, safe=''),params={'sessionToken':token},
            field_mask='id,displayName,formattedAddress,googleMapsUri,types')
        if not result.get('id') or not result.get('displayName',{}).get('text'):
            raise PlacesUnavailable('Place details are unavailable.')
        return {'id':result['id'],'name':result['displayName']['text'],
                'address':result.get('formattedAddress'), 'url':result.get('googleMapsUri'),
                'kind':'venue' if not any(t in result.get('types',[]) for t in ('locality','country','administrative_area_level_1','administrative_area_level_2','neighborhood','postal_town','postal_code','sublocality')) else 'area'}
    from sqlmodel import Session
    with Session(session.get_bind()) as cache_session:
        return cached(cache_session,'google_places',{'place_id':place_id},fetch,ttl_seconds=1800)
