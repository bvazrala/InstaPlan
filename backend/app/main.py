"""FastAPI entry point. Run: uvicorn app.main:app --reload  (API docs at /docs)"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db
from app.routers import chats, checkins, expenses, options, trips, ws

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="InstaPlan API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (chats, trips, checkins, options, expenses, ws):
    app.include_router(module.router)


@app.get("/health", tags=["meta"])
def health():
    return {"ok": True}
