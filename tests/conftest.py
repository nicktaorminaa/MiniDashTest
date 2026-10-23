from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from minidash.app import create_app
from minidash.clock import ManualClock

# Friday 23 Oct 2026, 14:00 in New York (EDT, UTC-4). Every seeded restaurant except
# Late Night Noodles is open at this time.
START = datetime(2026, 10, 23, 18, 0, tzinfo=UTC)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def clock():
    return ManualClock(START)


@pytest.fixture
def client(db_path, clock):
    with TestClient(create_app(db_path, clock=clock, business_tz="America/New_York")) as c:
        yield c
