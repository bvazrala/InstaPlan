"""Shared Meta Muse Spark client (OpenAI-compatible Meta Model API). Used by muse_group.py and muse_private.py.

Every request is stateless: the model only knows what a single request sends it. Group requests are built
only from group data and private requests only from one member's data, so the two never mix.
"""

import json
from typing import Any

from openai import OpenAI

from app.config import get_settings
from app.privacy.context import PrivacyViolation


def model_id() -> str:
    """Standard models only. Contributor models (e.g. muse-spark-1.3-contributor) may use prompts to train
    Meta's models, and our prompts contain people's chats and private answers."""
    model = get_settings().muse_model
    if model.endswith("-contributor"):
        raise PrivacyViolation(f"{model} may train on prompts; use a Standard model such as muse-spark-1.3")
    return model


def _client() -> OpenAI:
    s = get_settings()
    return OpenAI(api_key=s.muse_api_key, base_url=s.muse_base_url)


def ask_json(system: str, user: str) -> dict[str, Any]:
    """One request, JSON out. Validate the result with a Pydantic model at the call site."""
    res = _client().chat.completions.create(
        model=model_id(),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},  # Muse supports structured output; switch to json_schema once tested
    )
    return json.loads(res.choices[0].message.content or "{}")
