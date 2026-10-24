"""Gemini: the private assistant. Runs each member's private check-in (R9, R22).

PRIVACY: receives one member's PrivateContext and nothing about other members. Never send raw transactions,
account numbers or full names; budget ceilings are computed in app/logic/budget.py and passed in as numbers.
Use an API key from a billing-enabled project: on unpaid quota, Google may use prompts to improve its products.
"""

import json
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import get_settings
from app.privacy.context import PrivateContext, require_private_context
from app.schemas import PrivatePrefsData

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"


class CheckInTurn(BaseModel):
    reply: str  # what the assistant says next in the private thread
    prefs: PrivatePrefsData  # the member's updated private preferences
    done: bool = False  # true once budget, needs and no-gos are covered


def _client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)


def checkin_turn(ctx: PrivateContext, history: list[dict], user_text: str | None) -> CheckInTurn:
    """One turn of the private check-in. `user_text=None` starts the thread."""
    ctx = require_private_context(ctx)
    payload = {
        "first_name": ctx.first_name,
        "current_prefs": ctx.prefs.model_dump(),
        "suggested_ceiling": ctx.suggested_ceiling,
        "history": history,
        "user_message": user_text,
    }
    res = _client().models.generate_content(
        model=get_settings().gemini_model,
        contents=json.dumps(payload),
        config=types.GenerateContentConfig(
            system_instruction=(PROMPTS / "private_checkin.md").read_text(),
            response_mime_type="application/json",
            response_schema=CheckInTurn,
        ),
    )
    return res.parsed if isinstance(res.parsed, CheckInTurn) else CheckInTurn.model_validate_json(res.text or "{}")
