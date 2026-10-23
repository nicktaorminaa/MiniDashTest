"""The customer web page and the settings it needs from the server."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from minidash.routes.deps import BusinessTz, ClockDep
from minidash.services.scheduling import MAX_HORIZON, MIN_LEAD, RELEASE_BEFORE
from minidash.timeutil import to_db

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

router = APIRouter(tags=["web"])


@router.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@router.get("/config")
def config(clock: ClockDep, tz: BusinessTz) -> dict:
    """Rules and time the page needs, so it never hard-codes them.

    `now` is the server's clock (the injected one), so the page's hints agree with the server
    even when the clock is a ManualClock in a demo or test.
    """
    return {
        "now": to_db(clock.now()),
        "business_timezone": tz.key,
        "min_lead_minutes": int(MIN_LEAD.total_seconds() // 60),
        "max_horizon_days": MAX_HORIZON.days,
        "release_before_minutes": int(RELEASE_BEFORE.total_seconds() // 60),
    }
