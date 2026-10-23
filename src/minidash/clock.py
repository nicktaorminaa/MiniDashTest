"""Clocks. Application code asks a Clock for the time instead of calling datetime.now()."""

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current time as a timezone-aware datetime."""
        ...


class SystemClock:
    """The real clock, in UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class ManualClock:
    """A clock that only moves when told to. Used by tests and the demo script."""

    def __init__(self, start: datetime):
        self._now = _require_aware(start)

    def now(self) -> datetime:
        return self._now

    def set(self, when: datetime) -> None:
        self._now = _require_aware(when)

    def advance(self, delta: timedelta) -> None:
        # Add in UTC: adding to a ZoneInfo datetime is wall-clock arithmetic (wrong on DST nights).
        tz = self._now.tzinfo
        self._now = (self._now.astimezone(UTC) + delta).astimezone(tz)


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("ManualClock needs a timezone-aware datetime")
    return value
