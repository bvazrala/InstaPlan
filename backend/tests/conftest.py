"""Test setup: in-memory SQLite (or TEST_DATABASE_URL), a fresh encryption key, and fake auth via the X-Test-User header."""

import os

from cryptography.fernet import Fernet

# Tests drop and recreate every table, so they never read DATABASE_URL. To run them on a scratch Postgres,
# set TEST_DATABASE_URL (never your Supabase database).
os.environ.update(DATABASE_URL=os.environ.get("TEST_DATABASE_URL", "sqlite://"), APP_ENV="test", DEMO_MODE="false",
                  PRIVATE_DATA_KEY=Fernet.generate_key().decode(), SUPABASE_URL="", MUSE_API_KEY="")

import pytest
from fastapi import Header
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from app.auth import CurrentUser, get_current_user
from app.db import engine, init_db
from app.main import app
from app.models import Chat, ChatMember, Trip, User


def fake_user(x_test_user: str = Header(default="")) -> CurrentUser:
    return CurrentUser(id=x_test_user)


@pytest.fixture()
def client():
    SQLModel.metadata.drop_all(engine)
    init_db()
    app.dependency_overrides[get_current_user] = fake_user
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def world(client):
    """Alice, Bob and Cara share a chat with an open trip. Dan is an outsider."""
    with Session(engine) as s:
        for uid in ("alice", "bob", "cara", "dan"):
            s.add(User(id=uid, display_name=uid.title(), handle=uid, home_airport="AUS"))
        chat = Chat(id="test-chat", name="crew")
        s.add(chat)
        s.commit()
        for uid in ("alice", "bob", "cara"):
            s.add(ChatMember(chat_id=chat.id, user_id=uid))
        trip = Trip(id="test-trip", chat_id=chat.id, created_by="alice", stage="checkin")
        s.add(trip)
        s.commit()
        return {"chat_id": chat.id, "trip_id": trip.id}


def as_user(uid: str) -> dict[str, str]:
    return {"X-Test-User": uid}
