"""Scheduled-order rules.

The three numbers in Track A (45 minutes, 7 days, 30 minutes) live only in this module.
"""

from datetime import UTC, datetime, timedelta

from minidash.errors import DomainError

MIN_LEAD = timedelta(minutes=45)
MAX_HORIZON = timedelta(days=7)
RELEASE_BEFORE = timedelta(minutes=30)


def validate_schedule(scheduled_for: datetime, now: datetime) -> datetime:
    """Check the lead time and horizon of a requested delivery time and return release_at (UTC).

    Both values are converted to UTC before subtracting. Python subtracts two datetimes that
    share a tzinfo object by wall-clock time, which is wrong across a daylight-saving change.
    """
    if scheduled_for.tzinfo is None or scheduled_for.utcoffset() is None:
        raise DomainError(
            "SCHEDULE_TIMEZONE_REQUIRED",
            "scheduled_for must include a UTC offset, e.g. 2026-10-24T19:00:00-04:00",
        )
    scheduled_utc = scheduled_for.astimezone(UTC)
    lead = scheduled_utc - now.astimezone(UTC)
    if lead < MIN_LEAD:
        raise DomainError("SCHEDULE_TOO_SOON", "scheduled_for must be at least 45 minutes from now")
    if lead > MAX_HORIZON:
        raise DomainError("SCHEDULE_TOO_FAR", "scheduled_for must be at most 7 days from now")
    return scheduled_utc - RELEASE_BEFORE
