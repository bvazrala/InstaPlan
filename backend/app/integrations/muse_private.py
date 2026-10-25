"""Muse, private side: runs one member's private check-in (R9, R22).

PRIVACY: each request carries one member's PrivateContext and their own thread, nothing about anyone else.
It is a separate, stateless request from every group request, so private answers never reach the group side.
Never send raw transactions, account numbers or full names; budget ceilings come from app/logic/budget.py as numbers.
"""

import json
from pathlib import Path

from pydantic import BaseModel

from app.integrations.muse_client import ask_json
from app.privacy.context import PrivateContext, require_private_context
from app.schemas import PrivatePrefsData

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"


class CheckInTurn(BaseModel):
    reply: str  # what the assistant says next in the private thread
    prefs: PrivatePrefsData  # the member's updated private preferences
    done: bool = False  # true once budget, needs and no-gos are covered


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
    system = (PROMPTS / "private_checkin.md").read_text()
    schema = json.dumps(CheckInTurn.model_json_schema())
    return CheckInTurn.model_validate(ask_json(f"{system}\n\nJSON schema for your reply:\n{schema}", json.dumps(payload)))
