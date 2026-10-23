"""S3: lead-time and horizon rule (AC-3, AC-4, AC-5)."""

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from minidash.errors import DomainError
from minidash.services.scheduling import validate_schedule

NOW = datetime(2026, 10, 23, 18, 0, tzinfo=UTC)


def code_for(scheduled_for, now=NOW):
    with pytest.raises(DomainError) as exc:
        validate_schedule(scheduled_for, now)
    return exc.value.code


@pytest.mark.parametrize(
    "lead, accepted",
    [
        (timedelta(minutes=44, seconds=59), False),
        (timedelta(minutes=45) - timedelta(microseconds=1), False),
        (timedelta(minutes=45), True),
        (timedelta(minutes=46), True),
    ],
)
def test_lead_time_boundaries(lead, accepted):
    if accepted:
        validate_schedule(NOW + lead, NOW)
    else:
        assert code_for(NOW + lead) == "SCHEDULE_TOO_SOON"


def test_past_time_is_too_soon():
    assert code_for(NOW - timedelta(hours=1)) == "SCHEDULE_TOO_SOON"


@pytest.mark.parametrize(
    "lead, accepted",
    [
        (timedelta(days=7), True),
        (timedelta(days=7, microseconds=1), False),
        (timedelta(days=8), False),
    ],
)
def test_horizon_boundaries(lead, accepted):
    if accepted:
        validate_schedule(NOW + lead, NOW)
    else:
        assert code_for(NOW + lead) == "SCHEDULE_TOO_FAR"


def test_naive_datetime_rejected():
    assert code_for(datetime(2026, 10, 23, 20, 0)) == "SCHEDULE_TIMEZONE_REQUIRED"


def test_release_at_is_30_minutes_earlier_in_utc():
    eastern = timezone(timedelta(hours=-4))
    release_at = validate_schedule(datetime(2026, 10, 23, 19, 0, tzinfo=eastern), NOW)
    assert release_at == datetime(2026, 10, 23, 22, 30, tzinfo=UTC)
    assert release_at.utcoffset() == timedelta(0)


def test_lead_uses_real_elapsed_time_across_dst_fall_back():
    # 1 Nov 2026: New York clocks go from 01:59 EDT back to 01:00 EST.
    ny = ZoneInfo("America/New_York")
    now = datetime(2026, 11, 1, 0, 50, tzinfo=ny)  # 04:50 UTC
    scheduled = datetime(2026, 11, 1, 1, 30, fold=1, tzinfo=ny)  # 01:30 EST = 06:30 UTC
    # Wall clocks differ by 40 minutes, but 100 real minutes pass. This must be accepted.
    release_at = validate_schedule(scheduled, now)
    assert release_at == datetime(2026, 11, 1, 6, 0, tzinfo=UTC)
