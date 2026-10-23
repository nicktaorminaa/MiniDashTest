"""S2: schedule columns, migration of baseline databases, stored time format (AC-15)."""

import sqlite3
from datetime import UTC, datetime, timedelta, timezone

import pytest

from minidash.db import SCHEDULE_COLUMNS, check_sqlite_version, connect, init_db
from minidash.timeutil import to_db

BASELINE_ORDERS_DDL = """
CREATE TABLE restaurants (id INTEGER PRIMARY KEY, name TEXT NOT NULL, cuisine TEXT NOT NULL,
    opens_at TEXT NOT NULL, closes_at TEXT NOT NULL, avg_prep_minutes INTEGER NOT NULL);
CREATE TABLE orders (id INTEGER PRIMARY KEY,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id), status TEXT NOT NULL,
    total_cents INTEGER NOT NULL, address TEXT NOT NULL, created_at TEXT NOT NULL);
INSERT INTO restaurants VALUES (1, 'Old Place', 'Diner', '08:00', '20:00', 10);
INSERT INTO orders VALUES (1, 1, 'DELIVERED', 999, '9 Old Rd', '2026-01-01T00:00:00+00:00');
"""


def columns(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return {row[1] for row in conn.execute("PRAGMA table_info(orders)")}
    finally:
        conn.close()


def test_new_database_has_schedule_columns(db_path):
    init_db(db_path)
    assert set(SCHEDULE_COLUMNS) <= columns(db_path)


def test_baseline_database_is_migrated_without_losing_rows(db_path):
    raw = sqlite3.connect(db_path)
    raw.executescript(BASELINE_ORDERS_DDL)
    raw.close()
    assert not set(SCHEDULE_COLUMNS) & columns(db_path)

    init_db(db_path)
    init_db(db_path)  # second run must be a no-op, not an error

    assert set(SCHEDULE_COLUMNS) <= columns(db_path)
    conn = connect(db_path)
    row = conn.execute("SELECT * FROM orders WHERE id = 1").fetchone()
    conn.close()
    assert (row["status"], row["total_cents"], row["address"]) == ("DELIVERED", 999, "9 Old Rd")
    assert row["scheduled_for"] is None and row["release_at"] is None


def test_to_db_is_fixed_width_utc():
    assert to_db(datetime(2026, 10, 24, 19, 0, tzinfo=timezone(timedelta(hours=-4)))) == (
        "2026-10-24T23:00:00.000000+00:00"
    )


def test_to_db_text_order_matches_time_order():
    plus_five = timezone(timedelta(hours=5))
    times = [
        datetime(2026, 10, 24, 23, 0, 0, 1, tzinfo=UTC),
        datetime(2026, 10, 25, 3, 59, 59, tzinfo=plus_five),  # 22:59:59 UTC
        datetime(2026, 10, 24, 23, 0, tzinfo=UTC),
        datetime(
            2026, 10, 24, 18, 0, 0, 500, tzinfo=timezone(timedelta(hours=-5))
        ),  # 23:00:00.0005
    ]
    assert sorted(times) == sorted(times, key=to_db)


def test_to_db_rejects_naive():
    with pytest.raises(ValueError):
        to_db(datetime(2026, 10, 24, 19, 0))


def test_order_response_has_null_schedule_fields(client):
    order = {"restaurant_id": 1, "items": [{"menu_item_id": 1, "quantity": 1}], "address": "x"}
    body = client.post("/orders", json=order).json()
    fetched = client.get(f"/orders/{body['id']}").json()
    for field in ("scheduled_for", "release_at", "released_at"):
        assert field in fetched and fetched[field] is None


def test_old_sqlite_is_rejected_with_a_clear_message():
    with pytest.raises(RuntimeError, match="3.35"):
        check_sqlite_version((3, 31, 1))
    check_sqlite_version((3, 35, 0))
