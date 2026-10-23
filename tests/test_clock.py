"""S1: the app takes time from an injected clock (AC-14)."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from minidash.clock import ManualClock, SystemClock

from .conftest import START

ORDER = {"restaurant_id": 1, "items": [{"menu_item_id": 1, "quantity": 1}], "address": "1 Main St"}


def test_manual_clock_set_and_advance():
    clock = ManualClock(START)
    assert clock.now() == START
    clock.advance(timedelta(minutes=90))
    assert clock.now() == START + timedelta(minutes=90)
    later = datetime(2026, 12, 1, 9, 30, tzinfo=timezone(timedelta(hours=-5)))
    clock.set(later)
    assert clock.now() == later


def test_manual_clock_rejects_naive_datetimes():
    with pytest.raises(ValueError):
        ManualClock(datetime(2026, 10, 23, 12, 0))
    clock = ManualClock(START)
    with pytest.raises(ValueError):
        clock.set(datetime(2026, 10, 23, 12, 0))


def test_system_clock_is_aware_utc():
    now = SystemClock().now()
    assert now.utcoffset() == timedelta(0)


def test_created_at_comes_from_injected_clock(client, clock):
    clock.set(datetime(2027, 1, 2, 3, 4, 5, tzinfo=UTC))
    body = client.post("/orders", json=ORDER).json()
    assert datetime.fromisoformat(body["created_at"]) == datetime(2027, 1, 2, 3, 4, 5, tzinfo=UTC)


def test_advance_moves_real_time_across_dst_fall_back():
    from zoneinfo import ZoneInfo

    ny = ZoneInfo("America/New_York")
    clock = ManualClock(datetime(2026, 11, 1, 1, 30, tzinfo=ny))  # 01:30 EDT = 05:30 UTC
    clock.advance(timedelta(hours=1))
    assert clock.now().astimezone(UTC) == datetime(2026, 11, 1, 6, 30, tzinfo=UTC)
    assert clock.now().tzinfo is ny  # keeps the caller's zone for display
