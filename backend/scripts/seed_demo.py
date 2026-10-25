"""Seed the demo, checking every step and explaining any failure.

Creates 4 demo users in Supabase Auth, one group chat with the scripted conversation, and optionally
Nessie sandbox customers. Secrets are never printed, so the output is safe to share.

Run from backend/:
    python -m scripts.seed_demo            seed (Supabase Auth + database)
    python -m scripts.seed_demo --check    run every check, write nothing
    python -m scripts.seed_demo --nessie   also create Nessie customers, accounts and bills
    python -m scripts.seed_demo --debug    show full tracebacks
"""

import os
import socket
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

import httpx

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

DEBUG = "--debug" in sys.argv
_SECRETS: list[str] = []  # every secret value, scrubbed from anything printed


class StepFailed(Exception):
    pass


# ── Output helpers ────────────────────────────────────────────────────────────

def scrub(text: str) -> str:
    for s in _SECRETS:
        if s and len(s) >= 6:
            text = text.replace(s, "***")
    return text


def header(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 60 - len(title)))


def ok(msg: str) -> None:
    print(f"  ✅ {scrub(msg)}")


def info(msg: str) -> None:
    print(f"     {scrub(msg)}")


def warn(msg: str) -> None:
    print(f"  ⚠️  {scrub(msg)}")


def fail(msg: str, fix: str) -> StepFailed:
    print(f"  ❌ {scrub(msg)}")
    print(f"     Fix: {scrub(fix)}")
    return StepFailed(msg)


def key_kind(key: str) -> str:
    if not key:
        return "missing"
    for prefix in ("sb_publishable_", "sb_secret_"):
        if key.startswith(prefix):
            return f"{prefix}… ({len(key)} chars)"
    if key.startswith("eyJ"):
        return f"legacy JWT key ({len(key)} chars)"
    return f"unrecognized format ({len(key)} chars)"


def first_line(exc: BaseException) -> str:
    return scrub(str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__)


# ── Step 1: configuration ─────────────────────────────────────────────────────

def check_config():
    header("1. Configuration")
    info(f"Python {sys.version.split()[0]}, running in {Path.cwd()}")
    if not (Path.cwd() / ".env").exists():
        raise fail("No .env file in this folder.", "cd into backend/ and run: cp .env.example .env, then fill it in.")
    ok(".env found")

    try:
        from app.config import get_settings
        s = get_settings()
    except Exception as exc:
        raise fail(f"Could not read .env: {first_line(exc)}", "Check for typos or stray quotes in .env.") from exc

    from sqlalchemy.engine import make_url
    _SECRETS.extend([s.supabase_secret_key, s.supabase_publishable_key, s.private_data_key,
                     s.muse_api_key, s.serpapi_key, s.nessie_api_key])
    try:
        url = make_url(s.database_url)
    except Exception as exc:
        raise fail(f"DATABASE_URL can't be parsed: {first_line(exc)}",
                   "It must be one line, no quotes or spaces, like postgresql+psycopg://USER:PASSWORD@HOST:5432/postgres") from exc

    if url.drivername.startswith("sqlite"):
        warn(f"DATABASE_URL is SQLite ({url.database}): local database only. Fine for development.")
    else:
        info(f"DATABASE_URL → {url.render_as_string(hide_password=True)}")
        if url.drivername != "postgresql+psycopg":
            raise fail(f"Driver is '{url.drivername}'.", "Start the URL with postgresql+psycopg:// instead of postgresql://")
        if "YOUR-PASSWORD" in s.database_url or not url.password:
            raise fail("The password is missing or still says [YOUR-PASSWORD].",
                       "Replace [YOUR-PASSWORD] (brackets included) with your database password.")
        _SECRETS.append(url.password)
        if url.port == 6543:
            raise fail("Port 6543 is the transaction pooler.", "In Supabase → Connect, choose Session pooler (port 5432) and copy that string.")
        if url.host and url.host.endswith("pooler.supabase.com") and not (url.username or "").startswith("postgres."):
            raise fail(f"Pooler username is '{url.username}'.", "Pooler usernames look like postgres.PROJECT_REF. Copy the string from Connect.")
        ok("DATABASE_URL looks well formed")

    if s.supabase_url:
        if not s.supabase_url.startswith("https://") or s.supabase_url.endswith("/"):
            raise fail(f"SUPABASE_URL is '{s.supabase_url}'.", "Use https://PROJECT_REF.supabase.co with no trailing slash.")
        ok(f"SUPABASE_URL = {s.supabase_url}")
    else:
        warn("SUPABASE_URL is empty: demo users will get local ids and nobody can log in.")
    info(f"SUPABASE_PUBLISHABLE_KEY: {key_kind(s.supabase_publishable_key)}")
    info(f"SUPABASE_SECRET_KEY:      {key_kind(s.supabase_secret_key)}")
    if s.supabase_secret_key.startswith("sb_publishable_"):
        raise fail("SUPABASE_SECRET_KEY holds the publishable key.", "Use the sb_secret_… key from Settings → API Keys.")
    if s.supabase_publishable_key.startswith("sb_secret_"):
        raise fail("SUPABASE_PUBLISHABLE_KEY holds a secret key.", "Use the sb_publishable_… key; never put a secret key there.")

    from cryptography.fernet import Fernet
    if not s.private_data_key:
        warn("PRIVATE_DATA_KEY is empty: private answers won't survive a restart.")
    else:
        try:
            Fernet(s.private_data_key.encode())
            ok("PRIVATE_DATA_KEY is a valid key")
        except Exception as exc:
            raise fail("PRIVATE_DATA_KEY is not a valid Fernet key.",
                       'Generate one: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"') from exc
    return s, url


# ── Step 2: network ───────────────────────────────────────────────────────────

def check_network(s, url) -> None:
    header("2. Network")
    if not url.drivername.startswith("sqlite"):
        host, port = url.host, url.port or 5432
        try:
            addrs = sorted({a[4][0] for a in socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)})
            ok(f"{host} resolves to {', '.join(addrs[:3])}")
        except socket.gaierror as exc:
            raise fail(f"Can't look up {host}: {exc}", "Check the host for typos; copy it exactly from Supabase → Connect.") from exc
        try:
            with socket.create_connection((host, port), timeout=6):
                ok(f"Can open a connection to {host}:{port}")
        except TimeoutError as exc:
            raise fail(f"Connecting to {host}:{port} timed out.",
                       "This network is likely blocking database ports (common on event and campus Wi-Fi). "
                       "Try a phone hotspot, or comment out DATABASE_URL to use SQLite locally.") from exc
        except OSError as exc:
            raise fail(f"Can't connect to {host}:{port}: {exc}",
                       "If the host looks right, try a phone hotspot. The direct db.* host needs IPv6; use the Session pooler.") from exc

    if s.supabase_url:
        try:
            res = httpx.get(f"{s.supabase_url}/auth/v1/health", headers={"apikey": s.supabase_publishable_key}, timeout=10)
        except httpx.HTTPError as exc:
            raise fail(f"Can't reach {s.supabase_url}: {first_line(exc)}", "Check SUPABASE_URL for typos and your internet connection.") from exc
        if res.status_code == 200:
            ok("Supabase Auth is reachable")
        elif res.status_code in (401, 403):
            raise fail(f"Supabase rejected the publishable key ({res.status_code}).", "Copy the sb_publishable_… key again from Settings → API Keys.")
        else:
            warn(f"Supabase Auth health returned {res.status_code}; continuing.")


# ── Step 3: database ──────────────────────────────────────────────────────────

DB_HINTS = [
    ("timed out", "The network is blocking the database port. Try a phone hotspot, or use SQLite locally."),
    ("password authentication failed", "Wrong database password. Reset it in Supabase (Settings → Database) and paste it again."),
    ("tenant or user not found", "Wrong pooler host or username. Copy the whole Session pooler string from Connect (aws-0 vs aws-1 matters)."),
    ("could not translate host name", "Host name typo. Copy it exactly from Supabase → Connect."),
    ("max client connections", "Too many open connections. Stop other running backends and try again."),
    ("ssl", "SSL problem. Make sure you copied the Session pooler string, not a custom host."),
    ("permission denied", "The database user lacks permissions. Use the postgres user from the Connect string."),
]


def check_database(write: bool) -> None:
    header("3. Database")
    try:
        from sqlalchemy import text

        from app.db import engine, init_db
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        ok(f"Connected ({engine.dialect.name})")
        if write:
            init_db()
            from sqlmodel import SQLModel
            ok(f"{len(SQLModel.metadata.tables)} tables ready" + (", row-level security on" if engine.dialect.name == "postgresql" else ""))
    except StepFailed:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        hint = next((h for needle, h in DB_HINTS if needle in msg), "Run again with --debug and share the output.")
        if DEBUG:
            traceback.print_exc()
        raise fail(f"Database error: {first_line(exc)}", hint) from exc


# ── Step 4: Supabase Auth users ───────────────────────────────────────────────

def _auth_headers(key: str) -> dict[str, str]:
    headers = {"apikey": key}  # sb_secret_ keys go in the apikey header only
    if key.startswith("eyJ"):  # legacy service_role JWT
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _error_text(res: httpx.Response) -> str:
    try:
        body = res.json()
        return str(body.get("msg") or body.get("message") or body.get("error_description") or body.get("error") or body)
    except ValueError:
        return res.text[:200]


def auth_users(s, write: bool) -> dict[str, str]:
    header("4. Supabase Auth users")
    if not (s.supabase_url and s.supabase_secret_key):
        warn("Supabase isn't fully configured (SUPABASE_URL + SUPABASE_SECRET_KEY): using local ids demo-*.")
        return {key: f"demo-{key}" for key, *_ in PEOPLE}

    base, headers = f"{s.supabase_url}/auth/v1/admin/users", _auth_headers(s.supabase_secret_key)
    try:
        listing = httpx.get(base, headers=headers, params={"per_page": 200}, timeout=10)
    except httpx.HTTPError as exc:
        raise fail(f"Can't reach Supabase Auth: {first_line(exc)}", "Check your connection and SUPABASE_URL.") from exc
    if listing.status_code in (401, 403):
        raise fail(f"Secret key rejected ({listing.status_code}): {_error_text(listing)}",
                   "Paste the sb_secret_… key from Settings → API Keys into SUPABASE_SECRET_KEY.")
    if listing.status_code >= 300:
        raise fail(f"Listing users failed ({listing.status_code}): {_error_text(listing)}", "Share this output.")
    existing = {u.get("email"): u["id"] for u in listing.json().get("users", [])}
    ok(f"Secret key works ({len(existing)} users in this project)")

    ids: dict[str, str] = {}
    for key, *_ in PEOPLE:
        email = f"{key}@demo.instaplan.test"
        if email in existing:
            ids[key] = existing[email]
            info(f"{email:<30} already exists")
            continue
        if not write:
            info(f"{email:<30} would be created")
            ids[key] = f"demo-{key}"
            continue
        res = httpx.post(base, headers=headers, json={"email": email, "password": PASSWORD, "email_confirm": True}, timeout=10)
        if res.status_code >= 300:
            raise fail(f"Creating {email} failed ({res.status_code}): {_error_text(res)}",
                       "If it mentions the password, set DEMO_PASSWORD to something longer; otherwise share this output.")
        ids[key] = res.json()["id"]
        ok(f"{email:<30} created")
    return ids


# ── Step 5: demo data ─────────────────────────────────────────────────────────

def seed_data(ids: dict[str, str], with_nessie: bool) -> None:
    header("5. Demo data")
    from sqlmodel import Session, select

    from app.db import engine
    from app.integrations import nessie
    from app.models import Chat, ChatMember, Message, User

    with Session(engine) as session:
        for key, name, handle, airport, hue, balance, bill in PEOPLE:
            uid = ids[key]
            user = session.get(User, uid) or User(id=uid, display_name=name, handle=handle, home_airport=airport, hue=hue)
            if with_nessie and not user.nessie_customer_id:
                try:
                    customer = nessie.create_customer(name, "Demo")["objectCreated"]
                    account = nessie.create_account(customer["_id"], balance)["objectCreated"]
                    if bill:
                        nessie.create_bill(account["_id"], bill[0], bill[1], (date.today() + timedelta(days=20)).isoformat())
                    user.nessie_customer_id = customer["_id"]
                    ok(f"Nessie customer for {name}")
                except httpx.HTTPStatusError as exc:
                    raise fail(f"Nessie returned {exc.response.status_code}: {_error_text(exc.response)}",
                               "Check NESSIE_API_KEY. If it keeps failing, try NESSIE_BASE_URL=https://prod-api.nessieisreal.com") from exc
                except httpx.HTTPError as exc:
                    raise fail(f"Can't reach Nessie: {first_line(exc)}", "Check NESSIE_BASE_URL and your connection.") from exc
            session.add(user)
        session.commit()
        ok(f"{len(PEOPLE)} users saved")

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
            ok(f"Chat 'weekend crew ☕' created with {len(SCRIPT)} messages (id {chat.id})")
        else:
            ok(f"Chat 'weekend crew ☕' already exists (id {chat.id})")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    check_only = "--check" in sys.argv
    print("InstaPlan seed" + (" (check only, nothing is written)" if check_only else ""))
    try:
        s, url = check_config()
        check_network(s, url)
        check_database(write=not check_only)
        ids = auth_users(s, write=not check_only)
        if check_only:
            print("\nAll checks passed. Run without --check to seed.")
            return 0
        seed_data(ids, with_nessie="--nessie" in sys.argv)
    except StepFailed:
        print("\nStopped. Fix the item marked ❌ and run again.")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"\n  ❌ Unexpected {type(exc).__name__}: {first_line(exc)}")
        if DEBUG:
            print(scrub(traceback.format_exc()))
        else:
            print("     Run again with --debug for the full traceback.")
        return 1
    if ids.get("you", "").startswith("demo-"):
        print("\nDone (local only). Add SUPABASE_URL and SUPABASE_SECRET_KEY to .env to create real logins.")
    else:
        print(f"\nDone. Log in as you@demo.instaplan.test with password {PASSWORD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
