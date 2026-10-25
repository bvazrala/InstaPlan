"""Pure, evidence-gated widget projection. No fabricated fares, imagery or opening hours."""
import re
from datetime import UTC, datetime
from urllib.parse import urlparse
from app.schemas import WidgetSpecial


def public_url(value):
    if not isinstance(value,str) or any(part in value.casefold() for part in ('api_key=','access_token=','key=')):
        return None
    try:
        parsed=urlparse(value)
        return value if parsed.scheme in {'http','https'} and parsed.hostname and not parsed.username and not parsed.password else None
    except ValueError:
        return None


def requested_special(activity):
    value=(activity or '').casefold()
    if 'college football' in value or 'ncaa football' in value:
        return 'college_football'
    if 'concert' in value or 'live music' in value:
        return 'concert'
    return None


def event_for_venue(rows, venue_name, kind, *, retrieved_at, exact_date=None, venue_address=None):
    """Only an actual event at the recommended venue can supply its special slide."""
    if kind not in {'concert','college_football'}:
        return None
    normalize=lambda text: re.sub(r'[^a-z0-9]+',' ',str(text).casefold()).strip()
    for row in rows[:20] if isinstance(rows,list) else []:
        if not isinstance(row,dict):
            continue
        venue=row.get('venue') or {}
        if not isinstance(venue,dict) or normalize(venue.get('name')) != normalize(venue_name):
            continue
        if venue_address:
            known=set(normalize(venue_address).split()) - {'usa','united','states','us'}
            provider_address=' '.join(str(value) for value in row.get('address',[]) if isinstance(value,str)) if isinstance(row.get('address'),list) else ''
            observed=set(normalize(provider_address).split())
            if len(known & observed) < min(2,len(known)):
                continue
        title=row.get('title')
        if not isinstance(title,str) or not title.strip():
            continue
        if kind=='college_football' and not re.search(r'football|ncaa|ncaaf',title,re.I):
            continue
        date=row.get('date') or {}
        date_label=date.get('when') if isinstance(date,dict) else None
        image=public_url(row.get('image') or row.get('thumbnail'))
        tickets=row.get('ticket_info') or []
        booking=next((public_url(ticket.get('link')) for ticket in tickets if isinstance(ticket,dict) and public_url(ticket.get('link'))),None)
        if not date_label or not image or not booking:
            continue
        if exact_date and exact_date not in str(date_label) and exact_date != date.get('start_date'):
            continue  # A provider's month/day label cannot prove an approved exact year/date.
        return WidgetSpecial(id='event-'+str(row.get('event_token') or normalize(title)),kind=kind,
            image={'src':image,'alt':title},title=title,subtitle=venue_name,date_label=date_label,
            booking={'label':'View tickets','url':booking},provider='SerpApi Google Events',retrieved_at=retrieved_at)
    return None
