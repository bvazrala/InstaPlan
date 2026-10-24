"""Trip options (R12–R14). Responses carry only group-safe fields: see schemas.OptionOut."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.models import TripOption
from app.pipeline import generate_options
from app.privacy.access import require_trip_member
from app.schemas import OptionOut

router = APIRouter(tags=["options"])


@router.get("/trips/{trip_id}/options", response_model=list[OptionOut])
def list_options(trip_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    require_trip_member(session, trip_id, user)
    rows = session.exec(select(TripOption).where(TripOption.trip_id == trip_id).order_by(TripOption.fairest_rank)).all()  # type: ignore[arg-type]
    return [OptionOut.model_validate({**r.data, "id": r.id, "fairest_rank": r.fairest_rank, "priced_at": r.priced_at}) for r in rows]


@router.post("/trips/{trip_id}/options/generate", status_code=202)
def generate(trip_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    trip = require_trip_member(session, trip_id, user)
    try:
        generate_options(session, trip)
    except NotImplementedError as exc:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, str(exc)) from None
    return {"status": "started"}
