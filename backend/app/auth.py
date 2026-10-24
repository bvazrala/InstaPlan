"""Who is calling? Verifies Supabase access tokens. User ids never come from the request body or URL."""

from dataclasses import dataclass
from functools import lru_cache

import httpx
import jwt
from fastapi import Header, HTTPException, status

from app.config import get_settings

ASYMMETRIC_ALGS = {"ES256", "RS256", "EdDSA"}


@dataclass(frozen=True)
class CurrentUser:
    id: str  # Supabase user id (the token's `sub` claim)
    email: str | None = None


class InvalidToken(Exception):
    pass


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    url = f"{get_settings().supabase_url}/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(url, lifespan=600)  # Supabase caches JWKS for 10 minutes


def verify_token(token: str) -> CurrentUser:
    """Projects on JWT signing keys: verify locally against the JWKS.
    Legacy HS256 projects: ask Supabase Auth, as Supabase recommends instead of sharing the secret."""
    settings = get_settings()
    if not token or not settings.supabase_url:
        raise InvalidToken("missing token or Supabase not configured")
    try:
        alg = jwt.get_unverified_header(token).get("alg")
        if alg in ASYMMETRIC_ALGS:
            key = _jwks_client().get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token, key, algorithms=[alg],
                issuer=f"{settings.supabase_url}/auth/v1",
                options={"verify_aud": False},
            )
            return CurrentUser(id=claims["sub"], email=claims.get("email"))
        res = httpx.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={"apikey": settings.supabase_publishable_key, "Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if res.status_code != 200:
            raise InvalidToken("rejected by Supabase Auth")
        data = res.json()
        return CurrentUser(id=data["id"], email=data.get("email"))
    except (jwt.PyJWTError, httpx.HTTPError, KeyError) as exc:
        raise InvalidToken(str(exc)) from exc


def get_current_user(authorization: str = Header(default="")) -> CurrentUser:
    """FastAPI dependency for every REST route."""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        return verify_token(token)
    except InvalidToken:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from None
