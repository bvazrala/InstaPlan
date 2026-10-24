"""Caches third-party responses in Postgres so re-sorting, retries and the demo never re-hit rate limits."""

import hashlib
import json
from collections.abc import Callable
from typing import Any

from sqlmodel import Session

from app.models import ApiCache


def cache_key(provider: str, params: dict[str, Any]) -> str:
    raw = json.dumps({"provider": provider, **params}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def cached(session: Session, provider: str, params: dict[str, Any], fetch: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    key = cache_key(provider, params)
    hit = session.get(ApiCache, key)
    if hit is not None:
        return hit.response
    response = fetch()
    session.add(ApiCache(key=key, response=response))
    session.commit()
    return response
