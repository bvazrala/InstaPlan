"""WebSocket fan-out. Two kinds of channel:
- chat channel: every member of a chat (group messages, trip card, stage changes)
- user channel: one person's own connections (`private.*` events: their check-in thread)

The event type decides the channel, and the hub refuses to mix them up.
"""

import logging
from collections import defaultdict
from typing import Any, Protocol

from app.privacy.context import PrivacyViolation

log = logging.getLogger(__name__)


class Socket(Protocol):
    async def send_json(self, data: Any) -> None: ...


class Hub:
    def __init__(self) -> None:
        self._chat: dict[str, set[Socket]] = defaultdict(set)
        self._user: dict[str, set[Socket]] = defaultdict(set)

    def join(self, chat_id: str, user_id: str, ws: Socket) -> None:
        self._chat[chat_id].add(ws)
        self._user[user_id].add(ws)

    def leave(self, chat_id: str, user_id: str, ws: Socket) -> None:
        self._chat[chat_id].discard(ws)
        self._user[user_id].discard(ws)

    async def to_chat(self, chat_id: str, event: dict[str, Any]) -> None:
        if str(event.get("type", "")).startswith("private."):
            raise PrivacyViolation("private events can only go to their owner (use to_user)")
        await self._send(self._chat[chat_id], event)

    async def to_user(self, user_id: str, event: dict[str, Any]) -> None:
        if not str(event.get("type", "")).startswith("private."):
            raise ValueError("to_user is for private.* events; group events go through to_chat")
        await self._send(self._user[user_id], event)

    async def _send(self, sockets: set[Socket], event: dict[str, Any]) -> None:
        for ws in list(sockets):
            try:
                await ws.send_json(event)
            except Exception:  # noqa: BLE001  (closed connection; removed on disconnect)
                log.debug("dropping event for a closed socket")


hub = Hub()
