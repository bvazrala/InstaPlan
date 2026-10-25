"""Database engine and session. Tables are created at startup; no migrations this weekend."""

import logging
from collections.abc import Iterator

from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

log = logging.getLogger(__name__)


def _make_engine():
    url = get_settings().database_url
    if url.startswith("sqlite"):
        # In-memory SQLite (tests) needs one shared connection.
        extra = {"poolclass": StaticPool} if url in ("sqlite://", "sqlite:///:memory:") else {}
        return create_engine(url, connect_args={"check_same_thread": False}, **extra)
    return create_engine(url, pool_pre_ping=True)


engine = _make_engine()


def lockdown_statements(table_names: list[str], has_api_roles: bool = True) -> list[str]:
    """Supabase exposes the public schema through its Data API to anyone holding the publishable key
    (which is in the browser). Enabling RLS with no policies and revoking the API roles closes that door.
    The backend connects as `postgres`, which bypasses RLS, so it keeps full access."""
    stmts = []
    for name in table_names:
        table = f'public."{name}"'
        stmts.append(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        if has_api_roles:
            stmts.append(f"REVOKE ALL ON TABLE {table} FROM anon, authenticated")
    return stmts


def init_db() -> None:
    from app import models  # noqa: F401  (registers tables)

    SQLModel.metadata.create_all(engine)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            # Supabase has `anon` and `authenticated` roles; plain Postgres doesn't.
            has_api_roles = conn.execute(text("SELECT count(*) FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")).scalar() == 2
            for stmt in lockdown_statements(list(SQLModel.metadata.tables), has_api_roles):
                conn.execute(text(stmt))
        log.info("Row level security enabled on all tables")


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
