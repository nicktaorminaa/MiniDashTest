"""Application factory."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from zoneinfo import ZoneInfo

from fastapi import FastAPI

from minidash.clock import Clock, SystemClock
from minidash.db import init_db
from minidash.errors import DomainError, domain_error_handler
from minidash.routes import orders, restaurants
from minidash.worker import release_loop


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start the release loop with the app and stop it on shutdown."""
    task = None
    if app.state.release_interval > 0:
        task = asyncio.create_task(
            release_loop(app.state.db_path, app.state.clock, app.state.release_interval)
        )
    yield
    if task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def create_app(
    db_path: str | None = None,
    clock: Clock | None = None,
    business_tz: str | None = None,
    release_interval: float | None = None,
) -> FastAPI:
    """Build the app. Arguments override env vars MINIDASH_DB, MINIDASH_TZ and
    MINIDASH_RELEASE_INTERVAL (seconds; 0 turns the background release loop off)."""
    db_path = db_path or os.environ.get("MINIDASH_DB", "minidash.db")
    business_tz = business_tz or os.environ.get("MINIDASH_TZ", "America/New_York")
    if release_interval is None:  # not `or`: 0 is a valid value meaning "off"
        release_interval = float(os.environ.get("MINIDASH_RELEASE_INTERVAL", "15"))
    init_db(db_path)

    app = FastAPI(title="MiniDash", version="0.2.0", lifespan=lifespan)
    app.state.db_path = db_path
    app.state.clock = clock or SystemClock()
    app.state.business_tz = ZoneInfo(business_tz)
    app.state.release_interval = release_interval
    app.add_exception_handler(DomainError, domain_error_handler)
    app.include_router(restaurants.router)
    app.include_router(orders.router)
    return app
