"""Private check-ins (R9, R11, R22). OWNER ONLY.

Every route is under /trips/{trip_id}/me/ and acts on the logged-in user. No route here accepts a user id,
so there is no URL that could return someone else's answers.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.concurrency import run_in_threadpool
from sqlmodel import Session, delete, select

from app.auth import CurrentUser, get_current_user
from app.config import get_settings
from app.db import get_session
from app.integrations import muse_private, nessie
from app.logic.budget import Bill, default_reason, safe_to_spend
from app.models import PrivateMessage, PrivatePrefs, User
from app.privacy.access import require_trip_member
from app.privacy.context import PrivateContext
from app.privacy.crypto import decrypt_json, decrypt_text, encrypt_json, encrypt_text
from app.realtime import hub
from app.schemas import BudgetSuggestionOut, CheckInMessageOut, PrivatePrefsData, PrivateOrigin, SendMessageIn

router = APIRouter(prefix="/trips/{trip_id}/me", tags=["private (owner only)"])


def load_prefs(session: Session, trip_id: str, user_id: str) -> PrivatePrefsData:
    row = session.get(PrivatePrefs, (trip_id, user_id))
    return PrivatePrefsData.model_validate(decrypt_json(row.data_encrypted)) if row else PrivatePrefsData()


def save_prefs(session: Session, trip_id: str, user_id: str, prefs: PrivatePrefsData) -> None:
    session.merge(PrivatePrefs(trip_id=trip_id, user_id=user_id, data_encrypted=encrypt_json(prefs.model_dump())))
    session.commit()


def _thread(session: Session, trip_id: str, user_id: str) -> list[CheckInMessageOut]:
    rows = session.exec(select(PrivateMessage).where(PrivateMessage.trip_id == trip_id, PrivateMessage.user_id == user_id)
                        .order_by(PrivateMessage.sent_at)).all()  # type: ignore[arg-type]
    return [CheckInMessageOut(id=r.id, from_assistant=r.from_assistant, text=decrypt_text(r.body_encrypted), sent_at=r.sent_at)
            for r in rows]


@router.get("/private", response_model=PrivatePrefsData)
def get_my_private(trip_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    require_trip_member(session, trip_id, user)
    return load_prefs(session, trip_id, user.id)


@router.put("/private", response_model=PrivatePrefsData)
def put_my_private(trip_id: str, body: PrivatePrefsData, user: CurrentUser = Depends(get_current_user),
                   session: Session = Depends(get_session)):
    require_trip_member(session, trip_id, user)
    save_prefs(session, trip_id, user.id, body)
    return body


@router.delete("/private", status_code=204)
def delete_my_private(trip_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    """Members can delete their private answers and check-in thread at any time."""
    require_trip_member(session, trip_id, user)
    session.exec(delete(PrivatePrefs).where(PrivatePrefs.trip_id == trip_id, PrivatePrefs.user_id == user.id))  # type: ignore[call-overload]
    session.exec(delete(PrivateMessage).where(PrivateMessage.trip_id == trip_id, PrivateMessage.user_id == user.id))  # type: ignore[call-overload]
    session.commit()
    return Response(status_code=204)


@router.get("/checkin", response_model=list[CheckInMessageOut])
def my_checkin_thread(trip_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    require_trip_member(session, trip_id, user)
    return _thread(session, trip_id, user.id)


@router.post("/checkin", response_model=list[CheckInMessageOut])
async def reply_to_checkin(trip_id: str, body: SendMessageIn, user: CurrentUser = Depends(get_current_user),
                           session: Session = Depends(get_session)):
    """The member answers; Muse replies (a private, stateless request) and updates their private preferences."""
    require_trip_member(session, trip_id, user)
    if not get_settings().muse_api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Muse is not configured")
    me = session.get(User, user.id)
    ctx = PrivateContext(trip_id=trip_id, user_id=user.id, first_name=(me.display_name if me else "there").split()[0],
                         prefs=load_prefs(session, trip_id, user.id))
    history = [{"assistant" if m.from_assistant else "member": m.text} for m in _thread(session, trip_id, user.id)]
    turn = await run_in_threadpool(muse_private.checkin_turn, ctx, history, body.text)

    session.add(PrivateMessage(trip_id=trip_id, user_id=user.id, from_assistant=False, body_encrypted=encrypt_text(body.text)))
    reply = PrivateMessage(trip_id=trip_id, user_id=user.id, from_assistant=True, body_encrypted=encrypt_text(turn.reply))
    session.add(reply)
    session.commit()
    save_prefs(session, trip_id, user.id, turn.prefs)
    await hub.to_user(user.id, {"type": "private.checkin", "tripId": trip_id,
                                "message": {"id": reply.id, "from": "assistant", "kind": "text", "text": turn.reply}})
    return _thread(session, trip_id, user.id)


@router.get("/budget-suggestion", response_model=BudgetSuggestionOut)
def my_budget_suggestion(trip_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    """R11: safe-to-spend ceiling from the member's own Nessie account, computed in code (logic/budget.py)."""
    require_trip_member(session, trip_id, user)
    me = session.get(User, user.id)
    if me is None or not me.nessie_customer_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No linked account")
    accounts = nessie.accounts(me.nessie_customer_id)
    checking = next((a for a in accounts if a.get("type") == "Checking"), accounts[0] if accounts else None)
    if checking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No account found")
    horizon = (date.today() + timedelta(days=45)).isoformat()  # TODO: use the trip's end date once dates are structured
    due = [Bill(b.get("payee", "A bill"), float(b.get("payment_amount", 0)))
           for b in nessie.bills(checking["_id"])
           if b.get("status") in ("pending", "recurring") and str(b.get("payment_date", "")) <= horizon]
    ceiling = safe_to_spend(float(checking.get("balance", 0)), due)
    return BudgetSuggestionOut(amount=ceiling.amount, reason=default_reason(ceiling))


@router.put("/origin")
async def save_my_origin(trip_id: str, body: PrivateOrigin,
                         user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    trip = require_trip_member(session, trip_id, user)
    from app.logic.planner_service import require_planner, edit
    from app.logic.listening import public_text
    from app.schemas import PlannerEdit
    planner = require_planner(session, trip_id)
    if public_text(body.label) != body.label or any(char.isdigit() for char in body.label):
        raise HTTPException(422, "Share a city label without an address or coordinates.")
    # Only the coarse label crosses the public boundary. Coordinates stay encrypted and owner-only.
    prefs = load_prefs(session, trip_id, user.id)
    prefs.origin_location = body
    edit(session, planner, PlannerEdit(revision=planner.revision,field='where.origins',value=body.label), user.id)
    save_prefs(session, trip_id, user.id, prefs)
    await hub.to_chat(trip.chat_id, {'type':'planner.updated','tripId':trip_id})
    return {'label':body.label}
