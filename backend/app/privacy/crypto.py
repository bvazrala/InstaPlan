"""Encryption at rest for private columns (Fernet: AES-128-CBC + HMAC)."""

import json
import logging
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet

from app.config import get_settings

log = logging.getLogger(__name__)


@lru_cache
def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.private_data_key
    if not key:
        if settings.app_env != "dev":
            raise RuntimeError("PRIVATE_DATA_KEY must be set outside dev")
        log.warning("PRIVATE_DATA_KEY not set: using a throwaway key; private data won't survive a restart")
        key = Fernet.generate_key().decode()
    return Fernet(key.encode())


def encrypt_json(value: Any) -> str:
    return _fernet().encrypt(json.dumps(value).encode()).decode()


def decrypt_json(token: str) -> Any:
    return json.loads(_fernet().decrypt(token.encode()))


def encrypt_text(text: str) -> str:
    return encrypt_json(text)


def decrypt_text(token: str) -> str:
    return decrypt_json(token)
