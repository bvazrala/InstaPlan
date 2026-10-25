"""FastAPI entry point. Run: uvicorn app.main:app --reload  (API docs at /docs)"""

import logging
import asyncio
from contextlib import suppress
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db
from app.routers import chats, checkins, expenses, options, trips, ws, planner

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if get_settings().demo_mode:
        from app.db import engine
        from app.demo import seed_local_demo
        seed_local_demo(engine)
    from app.db import engine
    from app.planner_worker import run_listener
    listener = asyncio.create_task(run_listener(engine))
    try:
        yield
    finally:
        listener.cancel()
        with suppress(asyncio.CancelledError):
            await listener


app = FastAPI(title="InstaPlan API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys([get_settings().frontend_origin] + (
        ["http://localhost:3000", "http://127.0.0.1:3000"] if get_settings().demo_mode else []))),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (chats, trips, checkins, options, expenses, ws, planner):
    app.include_router(module.router)


@app.get("/health", tags=["meta"])
def health():
    from app.demo import DEMO_USER_ID
    settings = get_settings()
    return {"ok": True, "demoMode": settings.demo_mode,
            "demoUserId": DEMO_USER_ID if settings.demo_mode else None}
