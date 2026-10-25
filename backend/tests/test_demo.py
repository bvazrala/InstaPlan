"""Local demo sessions remain explicit, local, and subject to the privacy/access rules."""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlmodel import Session, select
from starlette.websockets import WebSocketDisconnect

from app.auth import InvalidToken, get_current_user, verify_token
from app.config import Settings, get_settings
from app.db import engine
from app.demo import DEMO_CHAT_ID, DEMO_TOKEN, DEMO_TRIP_ID, DEMO_USER_ID, seed_local_demo
from app.main import app
from app.models import Chat, Message, PrivatePrefs, Trip
from app.privacy.crypto import encrypt_json


@pytest.fixture()
def demo_client(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "app_env", "dev")
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app, client=("127.0.0.1", 50000)) as local:
        yield local


def test_demo_configuration_cannot_connect_to_configured_supabase():
    settings = Settings(_env_file=None, app_env="dev", demo_mode=True,
                        database_url="postgresql+psycopg://unused:unused@invalid.invalid/postgres")
    assert settings.effective_database_url == "sqlite:///./instaplan-demo.db"
    assert not Settings(_env_file=None, app_env="dev").demo_mode
    with pytest.raises(ValidationError, match="APP_ENV=dev"):
        Settings(_env_file=None, app_env="production", demo_mode=True)


def test_demo_token_is_not_accepted_in_normal_mode():
    assert not get_settings().demo_mode
    with pytest.raises(InvalidToken):
        verify_token(DEMO_TOKEN)


def test_demo_bootstraps_and_identifies_one_fixed_user(demo_client):
    health = demo_client.get("/health").json()
    assert health["demoMode"] and health["demoUserId"] == DEMO_USER_ID
    headers = {"Authorization": f"Bearer {DEMO_TOKEN}", "X-Demo-User": "demo-maya"}
    chats = demo_client.get("/chats", headers=headers)
    assert chats.status_code == 200 and chats.json()[0]["id"] == DEMO_CHAT_ID
    message = demo_client.post(f"/chats/{DEMO_CHAT_ID}/messages", headers=headers, json={"text": "Demo message"})
    assert message.status_code == 201 and message.json()["from"] == DEMO_USER_ID
    trip = demo_client.get(f"/chats/{DEMO_CHAT_ID}/trips/active", headers=headers).json()
    assert trip is None
    planner = demo_client.post(f"/chats/{DEMO_CHAT_ID}/planners",headers=headers,json={"title":"Dinner","topic":"Dining"})
    assert planner.status_code == 201 and planner.json()['status'] == 'collecting'
    assert planner.json()['poll']['approvals'] == []
    assert demo_client.get("/chats").status_code == 401
    assert demo_client.get("/chats", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_demo_still_checks_membership_and_private_ownership(demo_client):
    headers = {"Authorization": f"Bearer {DEMO_TOKEN}"}
    with Session(engine) as session:
        session.add(Trip(id=DEMO_TRIP_ID,chat_id=DEMO_CHAT_ID,created_by=DEMO_USER_ID))
        session.commit()
        session.add(Chat(id="outsider-chat", name="Not in this demo group"))
        session.add(PrivatePrefs(trip_id=DEMO_TRIP_ID, user_id="demo-maya",
                                data_encrypted=encrypt_json({"budget_cap": 8765, "no_gos": "PRIVATE-DEMO-SECRET"})))
        session.commit()
    assert demo_client.get("/chats/outsider-chat/members", headers=headers).status_code == 404
    response = demo_client.get(f"/trips/{DEMO_TRIP_ID}/me/private", headers=headers)
    assert response.json()["budgetCap"] is None
    assert "PRIVATE-DEMO-SECRET" not in response.text and "8765" not in response.text
    assert demo_client.get("/chats", headers={**headers, "Origin": "https://untrusted.example"}).status_code == 403


def test_demo_rejects_remote_clients(demo_client):
    with TestClient(app, client=("198.51.100.10", 50000)) as remote:
        assert remote.get("/chats", headers={"Authorization": f"Bearer {DEMO_TOKEN}"}).status_code == 403


def test_demo_seed_preserves_existing_work(demo_client):
    with Session(engine) as session:
        before = len(session.exec(select(Message)).all())
        trip = Trip(id=DEMO_TRIP_ID,chat_id=DEMO_CHAT_ID,created_by=DEMO_USER_ID,stage="options")
        session.add(trip)
        session.commit()
    seed_local_demo(engine)
    with Session(engine) as session:
        assert len(session.exec(select(Message)).all()) == before
        assert session.get(Trip, DEMO_TRIP_ID).stage == "options"


def test_demo_websocket_uses_same_identity_and_access_checks(demo_client):
    with demo_client.websocket_connect(f"/ws/chats/{DEMO_CHAT_ID}", headers={"origin": "http://localhost:3000"}) as ws:
        ws.send_json({"type": "auth", "token": DEMO_TOKEN})
        assert ws.receive_json()["type"] == "chat.ready"
        ws.send_json({"type": "message.send", "text": "Websocket local demo"})
        assert ws.receive_json()["message"]["from"] == DEMO_USER_ID
    with demo_client.websocket_connect("/ws/chats/non-member-chat") as ws:
        ws.send_json({"type": "auth", "token": DEMO_TOKEN})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()



def test_seed_cli_respects_demo_mode_without_contacting_supabase(demo_client, monkeypatch):
    import scripts.seed_demo as seed
    monkeypatch.setattr(seed, "auth_users", lambda *args, **kwargs: pytest.fail("Demo seed must not contact Supabase"))
    monkeypatch.setattr(seed, "check_network", lambda *args, **kwargs: pytest.fail("Demo seed must not contact Supabase"))
    monkeypatch.setattr(seed.sys, "argv", ["seed_demo", "--check"])
    assert seed.main() == 0


def test_demo_guard_errors_do_not_expose_configured_secrets():
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, app_env="production", demo_mode=True, private_data_key="SENSITIVE-CONFIG-KEY")
    assert "SENSITIVE-CONFIG-KEY" not in str(caught.value)
