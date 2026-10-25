"""Group chat (R21): chats, members, message history, sending."""

import asyncio

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.models import Chat, ChatMember, Message, User
from app.pipeline import on_group_message
from app.privacy.access import member_ids, require_chat_member
from app.realtime import hub
from app.schemas import ChatOut, MemberOut, MessageOut, SendMessageIn

router = APIRouter(tags=["chats"])


def message_out(m: Message) -> MessageOut:
    return MessageOut(id=m.id, from_=m.sender_id or "assistant", text=m.body, sent_at=m.sent_at)


async def post_group_message(session: Session, chat_id: str, user: CurrentUser, text: str, demo_speaker_id: str | None = None) -> MessageOut:
    """Shared by REST and WebSocket sends: store, broadcast, then run the pipeline in the background."""
    from app.logic.planner_service import active, speaker, enqueue
    actor = speaker(session, chat_id, user, demo_speaker_id)
    msg = Message(chat_id=chat_id, sender_id=actor, body=text)
    session.add(msg)
    session.flush()
    planner = active(session, chat_id)
    if planner:
        enqueue(session, planner, msg)
    session.commit()
    session.refresh(msg)
    out = message_out(msg)
    await hub.to_chat(chat_id, {"type": "message.new", "message": out.model_dump(mode="json", by_alias=True)})
    if not planner:
        asyncio.create_task(on_group_message(chat_id, msg.id))
    else:
        await hub.to_chat(chat_id, {"type":"planner.updated","tripId":planner.trip_id})
    return out


@router.get("/chats", response_model=list[ChatOut])
def my_chats(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    chats = session.exec(select(Chat).join(ChatMember).where(ChatMember.user_id == user.id)).all()
    return [ChatOut(id=c.id, name=c.name, group=c.is_group, members=member_ids(session, c.id)) for c in chats]


@router.get("/chats/{chat_id}/members", response_model=list[MemberOut])
def chat_members(chat_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    require_chat_member(session, chat_id, user)
    users = session.exec(select(User).where(User.id.in_(member_ids(session, chat_id)))).all()  # type: ignore[attr-defined]
    return [MemberOut(id=u.id, name=u.display_name, handle=u.handle, hue=u.hue, origin=u.home_airport) for u in users]


@router.get("/chats/{chat_id}/messages", response_model=list[MessageOut])
def chat_messages(chat_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    require_chat_member(session, chat_id, user)
    msgs = session.exec(select(Message).where(Message.chat_id == chat_id).order_by(Message.sent_at)).all()  # type: ignore[arg-type]
    return [message_out(m) for m in msgs]


@router.post("/chats/{chat_id}/messages", response_model=MessageOut, status_code=201)
async def send_message(chat_id: str, body: SendMessageIn, user: CurrentUser = Depends(get_current_user),
                       session: Session = Depends(get_session)):
    require_chat_member(session, chat_id, user)
    return await post_group_message(session, chat_id, user, body.text, body.demo_speaker_id)
