"""S4: the kitchen must be open for the whole window [release_at, scheduled_for] (AC-6)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from minidash.services.scheduling import kitchen_open_for_window

NY = ZoneInfo("America/New_York")
WINDOW = timedelta(minutes=30)


def window_open(opens, closes, start_local: datetime, tz=NY) -> bool:
    # Add the 30 minutes in UTC. Adding a timedelta to a ZoneInfo datetime is wall-clock
    # arithmetic and resets `fold`, which is wrong on DST nights.
    start = start_local.astimezone(UTC)
    return kitchen_open_for_window(opens, closes, start, start + WINDOW, tz)


def ny(day, hh, mm, fold=0):
    return datetime(2026, 10, day, hh, mm, fold=fold, tzinfo=NY)


@pytest.mark.parametrize(
    "start, expected",
    [
        (ny(23, 11, 0), True),  # release exactly at opening
        (ny(23, 10, 59), False),  # release one minute before opening
        (ny(23, 14, 0), True),
        (ny(23, 21, 30), True),  # delivery exactly at closing
        (ny(23, 21, 31), False),  # delivery one minute after closing
        (ny(23, 23, 0), False),
    ],
)
def test_same_day_hours(start, expected):
    assert window_open("11:00", "22:00", start) is expected


@pytest.mark.parametrize(
    "start, expected",
    [
        (ny(23, 17, 50), False),  # window starts before opening
        (ny(23, 18, 0), True),
        (ny(23, 23, 45), True),  # window crosses midnight
        (ny(24, 1, 30), True),  # after midnight, interval opened the previous evening
        (ny(24, 1, 31), False),  # delivery after 02:00
        (ny(24, 3, 0), False),
        (ny(24, 12, 0), False),
    ],
)
def test_overnight_hours(start, expected):
    assert window_open("18:00", "02:00", start) is expected


def test_equal_open_and_close_means_open_all_day():
    for hour in (0, 3, 12, 23):
        assert window_open("00:00", "00:00", ny(23, hour, 45))


def test_business_time_zone_changes_the_answer():
    start = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)  # 11:00 in New York, 08:00 in Los Angeles
    assert window_open("11:00", "22:00", start, NY)
    assert not window_open("11:00", "22:00", start, ZoneInfo("America/Los_Angeles"))


def test_fall_back_night_uses_real_time():
    # 1 Nov 2026, 01:00-01:59 happens twice in New York. The restaurant closes at the first
    # 01:30 (EDT, 05:30 UTC). A window from 01:00 to 01:30 EST (06:00-06:30 UTC) is after
    # closing even though its wall-clock times look like they fit.
    start = datetime(2026, 11, 1, 1, 0, fold=1, tzinfo=NY)
    assert start.astimezone(UTC) == datetime(2026, 11, 1, 6, 0, tzinfo=UTC)
    assert not window_open("18:00", "01:30", start)
