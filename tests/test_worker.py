"""S7: the background release loop and the CLI (AC-7, AC-10, AC-14)."""

import asyncio
import logging
import time
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from minidash import worker
from minidash.app import create_app
from minidash.clock import ManualClock
from minidash.db import connect, init_db
from minidash.repositories import orders as orders_repo

from .conftest import START

ORDER = {
    "restaurant_id": 1,
    "items": [{"menu_item_id": 1, "quantity": 1}],
    "address": "1 Main St",
    "scheduled_for": "2026-10-23T16:00:00-04:00",  # release_at 15:30 New York
}
RELEASE_AT = datetime(2026, 10, 23, 19, 30, tzinfo=UTC)


def wait_for_status(client, order_id, status, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if client.get(f"/orders/{order_id}").json()["status"] == status:
            return True
        time.sleep(0.02)
    return False


def make_client(db_path, clock, interval):
    app = create_app(
        db_path, clock=clock, business_tz="America/New_York", release_interval=interval
    )
    return TestClient(app)


def test_background_loop_releases_with_injected_clock(db_path):
    clock = ManualClock(START)
    with make_client(db_path, clock, interval=0.02) as client:
        order_id = client.post("/orders", json=ORDER).json()["id"]
        time.sleep(0.15)  # several loop ticks at 14:00 New York: nothing is due
        assert client.get(f"/orders/{order_id}").json()["status"] == "SCHEDULED"

        clock.set(RELEASE_AT)
        assert wait_for_status(client, order_id, "PLACED")
        assert client.get(f"/orders/{order_id}").json()["released_at"] == (
            "2026-10-23T19:30:00.000000+00:00"
        )


def insert_overdue_order(db_path):
    init_db(db_path)
    conn = connect(db_path)
    with conn:
        order_id = orders_repo.insert_order(
            conn,
            restaurant_id=1,
            status="SCHEDULED",
            total_cents=1450,
            address="1 Main St",
            created_at="2020-01-01T00:00:00.000000+00:00",
            items=[(1, 1, 1450)],
            scheduled_for="2020-01-01T01:00:00.000000+00:00",
            release_at="2020-01-01T00:30:00.000000+00:00",  # long past
        )
    conn.close()
    return order_id


def test_interval_zero_disables_the_loop(db_path):
    # The order is already due when the app starts. Any running loop releases it on its
    # first pass at startup, so this fails if 0 is mistaken for "use the default".
    order_id = insert_overdue_order(db_path)
    with make_client(db_path, ManualClock(START), interval=0) as client:
        time.sleep(0.15)
        assert client.get(f"/orders/{order_id}").json()["status"] == "SCHEDULED"


def test_loop_logs_a_failing_run_and_keeps_going(db_path, monkeypatch, caplog):
    init_db(db_path)
    calls = []
    real_run_once = worker.run_once

    def flaky(path, clock):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database went away")
        return real_run_once(path, clock)

    monkeypatch.setattr(worker, "run_once", flaky)
    caplog.set_level(logging.ERROR, logger="minidash.worker")

    async def run_briefly():
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(worker.release_loop(db_path, ManualClock(START), 0.01), 0.2)

    asyncio.run(run_briefly())
    assert len(calls) >= 3
    assert "release run failed" in caplog.text


def test_cli_once_releases_overdue_orders(db_path, capsys):
    order_id = insert_overdue_order(db_path)  # due by the real clock the CLI uses

    assert worker.main(["--db", db_path, "--once"]) == 0
    assert f"released 1 order(s): [{order_id}]" in capsys.readouterr().out
    conn = connect(db_path)
    assert orders_repo.get_order(conn, order_id)["status"] == "PLACED"
    conn.close()
