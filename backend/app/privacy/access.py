"""Membership checks used by every route. Non-members get 404, not 403, so they can't probe what exists."""

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.auth import CurrentUser
from app.config import get_settings
from app.models import Chat, ChatMember, Trip


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Not found")


def is_chat_member(session: Session, chat_id: str, user_id: str) -> bool:
    return session.get(ChatMember, (chat_id, user_id)) is not None


def require_chat_member(session: Session, chat_id: str, user: CurrentUser) -> Chat:
    chat = session.get(Chat, chat_id)
    if chat is None or not is_chat_member(session, chat_id, user.id):
        raise _not_found()
    return chat


def require_trip_member(session: Session, trip_id: str, user: CurrentUser) -> Trip:
    """Trip members are the members of the trip's group chat."""
    trip = session.get(Trip, trip_id)
    if trip is None or not is_chat_member(session, trip.chat_id, user.id):
        raise _not_found()
    return trip


def member_ids(session: Session, chat_id: str) -> list[str]:
    return list(session.exec(select(ChatMember.user_id).where(ChatMember.chat_id == chat_id)))


def private_budgets_allowed(group_size: int) -> bool:
    """In a group of 2, a dropped option would reveal the other person's budget."""
    return group_size >= get_settings().min_group_size_for_private_budgets
