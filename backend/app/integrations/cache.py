"""Expiring provider-response cache. Call with a dedicated session, never a domain transaction."""
import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session
from app.models import ApiCache

_SECRET_KEYS = {"api_key", "key", "authorization", "access_token", "secret"}


def sanitized(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: sanitized(v) for k, v in value.items() if k.lower() not in _SECRET_KEYS
                and k not in {"json_endpoint", "raw_html_file", "google_flights_url", "google_hotels_url"}}
    if isinstance(value, list):
        return [sanitized(v) for v in value]
    # Provider metadata can echo the authenticated request URL.
    if isinstance(value, str) and ("api_key=" in value.lower() or "access_token=" in value.lower()):
        return "<redacted provider URL>"
    return value


def cache_key(provider: str, params: dict[str, Any]) -> str:
    raw = json.dumps({"provider": provider, "params": sanitized(params)}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def cached(session: Session, provider: str, params: dict[str, Any], fetch: Callable[[], dict[str, Any]],
           *, ttl_seconds: int = 900, empty_ttl_seconds: int = 60,
           now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> dict[str, Any]:
    key = cache_key(provider, params)
    hit = session.get(ApiCache, key)
    def empty(response):
        return not any(response.get(k) for k in ("best_flights", "other_flights", "properties", "local_results"))
    if hit is not None:
        fetched = hit.fetched_at.replace(tzinfo=UTC) if hit.fetched_at.tzinfo is None else hit.fetched_at
        ttl = min(ttl_seconds, empty_ttl_seconds) if empty(hit.response) else ttl_seconds
        if now() - fetched < timedelta(seconds=ttl):
            return hit.response
    response = sanitized(fetch())  # exceptions never become cache entries
    if response.get("error") or response.get("search_metadata", {}).get("status") == "Error":
        raise ValueError("Provider returned an error response")
    if hit is None:
        session.add(ApiCache(key=key, response=response, fetched_at=now()))
    else:
        hit.response, hit.fetched_at = response, now()
        session.add(hit)
    try:
        session.commit()
    except IntegrityError:
        # Another independent worker inserted this key. Never rollback a trip transaction.
        session.rollback()
    return response
