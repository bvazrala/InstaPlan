"""Seed the demo so it never depends on live typing or Wi-Fi luck.

Creates 4 demo users (Supabase Auth if configured), one group chat, the scripted conversation, and
optionally Nessie sandbox customers with balances and bills.

Run from backend/:  python -m scripts.seed_demo            (local data only)
                    python -m scripts.seed_demo --nessie   (also create Nessie customers)
"""

import os
import sys
from datetime import date, timedelta

import httpx
from sqlmodel import Session, select

from app.config import get_settings
from app.db import engine, init_db
from app.integrations import nessie
from app.models import Chat, ChatMember, Message, User

PASSWORD = os.environ.get("DEMO_PASSWORD", "instaplan-demo-2026")

# (key, display name, handle, home airport, avatar hue, Nessie balance, bill before the trip)
PEOPLE = [
    ("you", "Jordan", "jordan", "AUS", 262, 1900, ("Rent", 890)),
    ("maya", "Maya", "maya.k", "AUS", 24, 2600, None),
    ("alex", "Alex", "alexr", "DFW", 200, 1500, ("Phone bill", 85)),
    ("sam", "Sam", "sam.t", "AUS", 330, 3200, None),
]

SCRIPT = [
    ("maya", "Okay, Saturday plans? Coffee and a little wandering? ☕"),
    ("you", "Yes! I'm free after 11 🙌"),
    ("sam", "I'm in! 11:30 at Juniper?"),
    ("maya", "we should do a trip over winter break, maybe NYC?"),
]


def supabase_user_id(email: str) -> str | None:
    """Creates the Auth user (or finds it) with the secret key. Returns None if Supabase isn't set up."""
    s = get_settings()
    key = s.supabase_secret_key
    if not (s.supabase_url and key):
        return None
    headers = {"apikey": key}  # sb_secret_ keys go in the apikey header only
    if key.startswith("eyJ"):  # legacy service_role JWT
        headers["Authorization"] = f"Bearer {key}"
    res = httpx.post(f"{s.supabase_url}/auth/v1/admin/users", headers=headers,
                     json={"email": email, "password": PASSWORD, "email_confirm": True}, timeout=10)
    if res.status_code < 300:
        return res.json()["id"]
    users = httpx.get(f"{s.supabase_url}/auth/v1/admin/users", headers=headers, timeout=10).json().get("users", [])
    return next((u["id"] for u in users if u.get("email") == email), None)


def seed(with_nessie: bool) -> None:
    init_db()
    with Session(engine) as session:
        ids: dict[str, str] = {}
        for key, name, handle, airport, hue, balance, bill in PEOPLE:
            email = f"{key}@demo.instaplan.test"
            uid = supabase_user_id(email) or f"demo-{key}"
            ids[key] = uid
            user = session.get(User, uid) or User(id=uid, display_name=name, handle=handle, home_airport=airport, hue=hue)
            if with_nessie and not user.nessie_customer_id:
                customer = nessie.create_customer(name, "Demo")["objectCreated"]
                account = nessie.create_account(customer["_id"], balance)["objectCreated"]
                if bill:
                    nessie.create_bill(account["_id"], bill[0], bill[1], (date.today() + timedelta(days=20)).isoformat())
                user.nessie_customer_id = customer["_id"]
            session.add(user)
            print(f"  {name:<7} {email:<32} id={uid}")

        chat = session.exec(select(Chat).where(Chat.name == "weekend crew ☕")).first()
        if chat is None:
            chat = Chat(name="weekend crew ☕")
            session.add(chat)
            session.commit()
            for uid in ids.values():
                session.add(ChatMember(chat_id=chat.id, user_id=uid))
            for key, text in SCRIPT:
                session.add(Message(chat_id=chat.id, sender_id=ids[key], body=text))
        session.commit()
        print(f"Chat '{chat.name}' id={chat.id}. Demo password: {PASSWORD}")


if __name__ == "__main__":
    seed(with_nessie="--nessie" in sys.argv)
