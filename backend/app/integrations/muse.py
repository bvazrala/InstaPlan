"""Meta Muse Spark: the group-facing assistant. Reads the group chat, writes group messages.

PRIVACY: every function here takes a GroupContext and calls require_group_context first.
Never pass budgets, bank data, private check-in answers or a PrivateContext to anything in this file.
"""

import json
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel

from app.config import get_settings
from app.privacy.context import GroupContext, GroupMessage, require_group_context

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"


class ExtractedFact(BaseModel):
    field: str  # Destination, Dates, From, Travel mode, Food, Activities, Lodging, Budget vibe
    value: str
    member_id: str | None = None  # who it applies to; None = whole group
    score: int | None = None  # -2..+2 if it's a like or dislike
    required: bool = False


class Extraction(BaseModel):
    facts: list[ExtractedFact] = []


def _client() -> OpenAI:
    s = get_settings()
    return OpenAI(api_key=s.muse_api_key, base_url=s.muse_base_url)


def _render(ctx: GroupContext) -> str:
    """The only way group data becomes prompt text."""
    ctx = require_group_context(ctx)
    return json.dumps(ctx.model_dump(), ensure_ascii=False)


def _ask_json(system: str, user: str) -> dict:
    res = _client().chat.completions.create(
        model=get_settings().muse_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},  # confirm structured-output support at the Meta booth
    )
    return json.loads(res.choices[0].message.content or "{}")


def detect_trip_intent(text: str) -> bool:
    """R2: does this group message propose a trip? Cheap check before calling the model."""
    keywords = ("trip", "travel", "vacation", "getaway", "road trip", "fly to", "visit")
    return any(k in text.lower() for k in keywords)


def extract_facts(ctx: GroupContext, new_message: GroupMessage) -> list[ExtractedFact]:
    """R3: turn one new group message into facts for the trip card."""
    system = (PROMPTS / "extract_facts.md").read_text()
    user = json.dumps({"context": json.loads(_render(ctx)), "new_message": new_message.model_dump()})
    return Extraction.model_validate(_ask_json(system, user)).facts


def write_nudge(ctx: GroupContext, missing_field: str) -> str:
    """R6: one short, friendly, tap-to-answer question for a missing required field."""
    system = (PROMPTS / "group_nudge.md").read_text()
    data = _ask_json(system, json.dumps({"context": json.loads(_render(ctx)), "missing_field": missing_field}))
    return str(data.get("question", f"Quick one: {missing_field}?"))
