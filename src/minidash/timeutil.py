"""How times are stored.

Every stored time is UTC with microseconds, e.g. 2026-10-24T23:00:00.000000+00:00. All values
have the same width and offset, so comparing them as text in SQL gives the same answer as
comparing the times.
"""

from datetime import UTC, datetime


def to_db(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("refusing to store a naive datetime")
    return value.astimezone(UTC).isoformat(timespec="microseconds")
