"""Scheduled-order rules.

The three numbers in Track A (45 minutes, 7 days, 30 minutes) live only in this module.
"""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

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


def kitchen_open_for_window(
    opens_at: str, closes_at: str, start: datetime, end: datetime, tz: ZoneInfo
) -> bool:
    """True if [start, end] lies inside one opening interval of a restaurant.

    opens_at/closes_at are local "HH:MM" times in `tz`. closes_at earlier than opens_at means the
    restaurant closes after midnight; equal values mean it is open all day. Both ends are
    inclusive. Interval ends are converted to UTC before comparing, for the same DST reason as
    validate_schedule.
    """
    opens, closes = _parse_hhmm(opens_at), _parse_hhmm(closes_at)
    if opens == closes:
        return True
    start_utc, end_utc = start.astimezone(UTC), end.astimezone(UTC)
    start_day = start.astimezone(tz).date()
    # An interval that opened yesterday evening can still cover a start time after midnight.
    for day in (start_day - timedelta(days=1), start_day):
        close_day = day if closes > opens else day + timedelta(days=1)
        open_utc = datetime.combine(day, opens, tzinfo=tz).astimezone(UTC)
        close_utc = datetime.combine(close_day, closes, tzinfo=tz).astimezone(UTC)
        if open_utc <= start_utc and end_utc <= close_utc:
            return True
    return False


def _parse_hhmm(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))
