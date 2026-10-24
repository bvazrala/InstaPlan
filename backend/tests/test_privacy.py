"""R23: friends never see each other's private information. Show this file to judges."""

import pytest
from sqlmodel import Session, select
from starlette.websockets import WebSocketDisconnect

from app.auth import CurrentUser
from app.db import engine
from app.integrations import muse
from app.main import app
from app.models import PrivateMessage, PrivatePrefs
from app.privacy.context import GroupContext, PrivacyViolation, PrivateContext
from app.privacy.crypto import encrypt_text
from app.realtime import Hub
from app.schemas import OptionOut, PrivatePrefsData
from tests.conftest import as_user

SECRET = {"budgetCap": 437, "dietary": ["SECRET-DIET"], "noGos": "SECRET-NOGO", "privateScores": {"SECRET-CITY": -2}}
MARKERS = ("437", "SECRET")


def _alice_saves_secrets(client, trip_id: str) -> None:
    res = client.put(f"/trips/{trip_id}/me/private", json=SECRET, headers=as_user("alice"))
    assert res.status_code == 200
    with Session(engine) as s:
        s.add(PrivateMessage(trip_id=trip_id, user_id="alice", from_assistant=False,
                             body_encrypted=encrypt_text("my budget is SECRET 437")))
        s.commit()


def test_owner_reads_own_private_answers(client, world):
    _alice_saves_secrets(client, world["trip_id"])
    res = client.get(f"/trips/{world['trip_id']}/me/private", headers=as_user("alice"))
    assert res.json()["noGos"] == "SECRET-NOGO"


def test_other_member_gets_their_own_empty_answers_not_alices(client, world):
    _alice_saves_secrets(client, world["trip_id"])
    res = client.get(f"/trips/{world['trip_id']}/me/private", headers=as_user("bob"))
    assert res.status_code == 200
    assert res.json()["budgetCap"] is None and "SECRET" not in res.text


def test_no_get_endpoint_leaks_private_data_to_another_member(client, world):
    """Sweeps every GET route in the app as Bob, after Alice saved private answers."""
    _alice_saves_secrets(client, world["trip_id"])
    params = {"chat_id": world["chat_id"], "trip_id": world["trip_id"], "fact_id": "none"}
    checked = 0
    for path, ops in app.openapi()["paths"].items():
        if "get" in ops and "{" in path:
            res = client.get(path.format(**params), headers=as_user("bob"))
            assert not any(m in res.text for m in MARKERS), f"{path} leaked private data"
            checked += 1
    assert checked >= 8


def test_outsider_cannot_see_trip_or_chat(client, world):
    for path in (f"/trips/{world['trip_id']}", f"/trips/{world['trip_id']}/facts",
                 f"/trips/{world['trip_id']}/me/private", f"/chats/{world['chat_id']}/messages"):
        assert client.get(path, headers=as_user("dan")).status_code == 404, path


def test_private_answers_are_encrypted_at_rest(client, world):
    _alice_saves_secrets(client, world["trip_id"])
    with Session(engine) as s:
        rows = [r.data_encrypted for r in s.exec(select(PrivatePrefs))] + [r.body_encrypted for r in s.exec(select(PrivateMessage))]
    assert rows and not any("SECRET" in r or "437" in r for r in rows)


def test_member_can_delete_private_answers(client, world):
    _alice_saves_secrets(client, world["trip_id"])
    assert client.delete(f"/trips/{world['trip_id']}/me/private", headers=as_user("alice")).status_code == 204
    assert client.get(f"/trips/{world['trip_id']}/me/private", headers=as_user("alice")).json()["noGos"] == ""


def test_group_view_shows_checkin_count_not_who(client, world):
    _alice_saves_secrets(client, world["trip_id"])
    body = client.get(f"/trips/{world['trip_id']}", headers=as_user("bob")).json()
    assert body["checkinsDone"] == 1 and "alice" not in str(body)


def test_muse_refuses_private_context():
    private = PrivateContext(trip_id="t", user_id="alice", first_name="Alice", prefs=PrivatePrefsData(budget_cap=437))
    with pytest.raises(PrivacyViolation):
        muse._render(private)  # type: ignore[arg-type]
    muse._render(GroupContext(trip_id="t", members=(), recent_messages=()))  # group context is fine


def test_private_context_is_redacted_in_logs():
    private = PrivateContext(trip_id="t", user_id="alice", first_name="Alice", prefs=PrivatePrefsData(budget_cap=437))
    assert "437" not in repr(private) and "437" not in str(private) and "437" not in f"{private}"


def test_options_never_carry_burden_or_ceilings():
    fields = " ".join(OptionOut.model_fields).lower()
    assert not any(word in fields for word in ("burden", "ceiling", "budget"))


class FakeSocket:
    def __init__(self):
        self.received = []

    async def send_json(self, data):
        self.received.append(data)


@pytest.mark.anyio
async def test_private_events_reach_only_their_owner():
    hub, alice, bob = Hub(), FakeSocket(), FakeSocket()
    hub.join("chat", "alice", alice)
    hub.join("chat", "bob", bob)
    await hub.to_user("alice", {"type": "private.checkin", "message": "budget?"})
    await hub.to_chat("chat", {"type": "message.new"})
    assert [e["type"] for e in alice.received] == ["private.checkin", "message.new"]
    assert [e["type"] for e in bob.received] == ["message.new"]


@pytest.mark.anyio
async def test_hub_refuses_to_broadcast_private_events():
    hub = Hub()
    with pytest.raises(PrivacyViolation):
        await hub.to_chat("chat", {"type": "private.checkin"})
    with pytest.raises(ValueError):
        await hub.to_user("alice", {"type": "message.new"})


def test_websocket_rejects_non_members(client, world, monkeypatch):
    monkeypatch.setattr("app.routers.ws.verify_token", lambda token: CurrentUser(id=token))
    with client.websocket_connect(f"/ws/chats/{world['chat_id']}") as ws:
        ws.send_json({"type": "auth", "token": "dan"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_websocket_member_receives_group_messages(client, world, monkeypatch):
    monkeypatch.setattr("app.routers.ws.verify_token", lambda token: CurrentUser(id=token))
    with client.websocket_connect(f"/ws/chats/{world['chat_id']}") as ws:
        ws.send_json({"type": "auth", "token": "bob"})
        ws.send_json({"type": "message.send", "text": "Dallas here"})
        event = ws.receive_json()
    assert event["type"] == "message.new" and event["message"]["text"] == "Dallas here"


@pytest.fixture
def anyio_backend():
    return "asyncio"
