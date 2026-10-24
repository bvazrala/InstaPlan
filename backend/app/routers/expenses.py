"""Settle up (R17): log shared expenses, suggest transfers, pay through Nessie."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.integrations import nessie
from app.logic.settle import equal_split, net_balances, suggest_transfers
from app.models import Expense, User
from app.privacy.access import member_ids, require_trip_member
from app.schemas import ApiModel, ExpenseIn, ExpenseOut, TransferOut

router = APIRouter(prefix="/trips/{trip_id}", tags=["settle up"])


class PayIn(ApiModel):
    to: str
    amount: float


def _transfers(session: Session, trip_id: str) -> list[TransferOut]:
    rows = session.exec(select(Expense).where(Expense.trip_id == trip_id)).all()
    net = net_balances((e.payer_id, e.amount_cents, e.split_cents) for e in rows)
    return [TransferOut(from_=t.from_id, to=t.to_id, amount=t.cents / 100) for t in suggest_transfers(net)]


@router.get("/expenses", response_model=list[ExpenseOut])
def list_expenses(trip_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    require_trip_member(session, trip_id, user)
    rows = session.exec(select(Expense).where(Expense.trip_id == trip_id)).all()
    return [ExpenseOut(id=e.id, description=e.description, payer_id=e.payer_id, amount=e.amount_cents / 100) for e in rows]


@router.post("/expenses", response_model=ExpenseOut, status_code=201)
def add_expense(trip_id: str, body: ExpenseIn, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    """The logged-in user paid; split evenly across the group."""
    trip = require_trip_member(session, trip_id, user)
    cents = round(body.amount * 100)
    e = Expense(trip_id=trip_id, payer_id=user.id, description=body.description, amount_cents=cents,
                split_cents=equal_split(cents, member_ids(session, trip.chat_id)))
    session.add(e)
    session.commit()
    return ExpenseOut(id=e.id, description=e.description, payer_id=e.payer_id, amount=cents / 100)


@router.get("/transfers", response_model=list[TransferOut])
def suggested_transfers(trip_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    require_trip_member(session, trip_id, user)
    return _transfers(session, trip_id)


@router.post("/transfers/pay", response_model=list[TransferOut])
def pay(trip_id: str, body: PayIn, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    """The logged-in user pays one suggested transfer from their own Nessie account."""
    require_trip_member(session, trip_id, user)
    if not any(t.from_ == user.id and t.to == body.to and abs(t.amount - body.amount) < 0.01 for t in _transfers(session, trip_id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Not a suggested transfer for you")
    me, payee = session.get(User, user.id), session.get(User, body.to)
    if not (me and me.nessie_customer_id and payee and payee.nessie_customer_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Both people need a linked account")
    nessie.transfer(nessie.accounts(me.nessie_customer_id)[0]["_id"], nessie.accounts(payee.nessie_customer_id)[0]["_id"],
                    body.amount, f"InstaPlan trip {trip_id[:6]}")
    # TODO: record the transfer on the expense so the suggestion disappears.
    return _transfers(session, trip_id)
