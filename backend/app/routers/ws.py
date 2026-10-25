"""WebSocket per chat. The first message must be {"type": "auth", "token": ...}; the token is never in the URL,
so it stays out of server logs. After auth, the socket receives its chat's group events and its own private events."""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from fastapi.concurrency import run_in_threadpool
from sqlmodel import Session

from app.auth import CurrentUser, InvalidToken, verify_token
from app.db import engine
from app.privacy.access import is_chat_member
from app.realtime import hub
from app.routers.chats import post_group_message

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/chats/{chat_id}")
async def chat_socket(ws: WebSocket, chat_id: str):
    await ws.accept()
    try:
        first = await asyncio.wait_for(ws.receive_json(), timeout=10)
        if first.get("type") != "auth":
            raise InvalidToken("first message must be auth")
        user: CurrentUser = await run_in_threadpool(verify_token, str(first.get("token") or ""))
    except (TimeoutError, InvalidToken, ValueError):
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    with Session(engine) as session:
        if not is_chat_member(session, chat_id, user.id):
            await ws.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    hub.join(chat_id, user.id, ws)
    await ws.send_json({"type": "chat.ready"})
    try:
        while True:
            event = await ws.receive_json()
            text = str(event.get("text", "")).strip()
            if event.get("type") == "message.send" and 0 < len(text) <= 2000:
                with Session(engine) as session:
                    await post_group_message(session, chat_id, user, text)
    except WebSocketDisconnect:
        pass
    finally:
        hub.leave(chat_id, user.id, ws)
