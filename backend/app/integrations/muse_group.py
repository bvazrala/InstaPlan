"""Muse, group side: reads the group chat and writes group messages (trip offer, facts, nudges).

PRIVACY: every function here takes a GroupContext and calls require_group_context first.
Never pass budgets, bank data, private check-in answers or a PrivateContext to anything in this file.
"""

import json
from pathlib import Path

from pydantic import BaseModel

from app.integrations.muse_client import ask_json
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


def _render(ctx: GroupContext) -> str:
    """The only way group data becomes prompt text."""
    ctx = require_group_context(ctx)
    return json.dumps(ctx.model_dump(), ensure_ascii=False)


def detect_trip_intent(text: str) -> bool:
    """R2: does this group message propose a trip? Cheap check before calling the model."""
    keywords = ("trip", "travel", "vacation", "getaway", "road trip", "fly to", "visit")
    return any(k in text.lower() for k in keywords)


def extract_facts(ctx: GroupContext, new_message: GroupMessage) -> list[ExtractedFact]:
    """R3: turn one new group message into facts for the trip card."""
    system = (PROMPTS / "extract_facts.md").read_text()
    user = json.dumps({"context": json.loads(_render(ctx)), "new_message": new_message.model_dump()})
    return Extraction.model_validate(ask_json(system, user)).facts


def write_nudge(ctx: GroupContext, missing_field: str) -> str:
    """R6: one short, friendly, tap-to-answer question for a missing required field."""
    system = (PROMPTS / "group_nudge.md").read_text()
    data = ask_json(system, json.dumps({"context": json.loads(_render(ctx)), "missing_field": missing_field}))
    return str(data.get("question", f"Quick one: {missing_field}?"))


def resolve_planning(ctx: GroupContext):
    """Resolve public facts only; a model suggestion is still validated by the engine."""
    from app.logic.planning import PlanningInput
    from datetime import date
    ctx = require_group_context(ctx)
    system = (PROMPTS / "resolve_planning.md").read_text()
    schema = json.dumps(PlanningInput.model_json_schema())
    return PlanningInput.model_validate(ask_json(system + "\nJSON schema:\n" + schema,
        json.dumps({"today": date.today().isoformat(), "context": json.loads(_render(ctx))})))


def listen_planner(ctx: GroupContext) -> dict:
    require_group_context(ctx)
    return ask_json((PROMPTS / "planner_listen.md").read_text(encoding="utf-8"), _render(ctx))


def predict_planner(ctx: GroupContext) -> dict:
    require_group_context(ctx)
    return ask_json((PROMPTS / "planner_predict.md").read_text(encoding="utf-8"), _render(ctx))
