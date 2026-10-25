"""Durable listener dispatcher; every task uses fresh database sessions."""
import asyncio
from fastapi.concurrency import run_in_threadpool
from sqlmodel import Session
from app.config import get_settings
from app.logic.planner_service import claim_batch, process_batch
from app.models import Trip
from app.realtime import hub

async def run_listener(engine):
    tasks = set()
    async def run(batch_id, lease):
        try:
            trip_id = await run_in_threadpool(process_batch, engine, batch_id, lease)
            if trip_id:
                with Session(engine) as session:
                    trip = session.get(Trip,trip_id)
                    chat_id = trip.chat_id if trip else None
                if chat_id:
                    await hub.to_chat(chat_id,{'type':'planner.updated','tripId':trip_id})
        except Exception:
            # Lease recovery retries interrupted work; never log prompts or provider errors.
            pass
    try:
        while True:
            if len(tasks) < get_settings().listener_concurrency:
                with Session(engine) as session:
                    claimed = claim_batch(session)
                if claimed:
                    task = asyncio.create_task(run(*claimed))
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
            await asyncio.sleep(.2)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
