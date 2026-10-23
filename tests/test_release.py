"""S6: releasing scheduled orders exactly once (AC-7 to AC-10)."""

import threading
from datetime import UTC, datetime, timedelta

import pytest

from minidash.db import connect, init_db
from minidash.repositories import orders as orders_repo
from minidash.services.scheduling import release_due_orders
from minidash.timeutil import to_db

RELEASE_AT = datetime(2026, 10, 23, 19, 30, tzinfo=UTC)  # for delivery at 16:00 New York
TINY = timedelta(microseconds=1)


@pytest.fixture
def conn(db_path):
    init_db(db_path)
    c = connect(db_path)
    yield c
    c.close()


def add_order(conn, status="SCHEDULED", release_at=RELEASE_AT):
    with conn:
        return orders_repo.insert_order(
            conn,
            restaurant_id=1,
            status=status,
            total_cents=1450,
            address="1 Main St",
            created_at=to_db(datetime(2026, 10, 23, 18, 0, tzinfo=UTC)),
            items=[(1, 1, 1450)],
            scheduled_for=to_db(release_at + timedelta(minutes=30)) if release_at else None,
            release_at=to_db(release_at) if release_at else None,
        )


def status_of(conn, order_id):
    row = orders_repo.get_order(conn, order_id)
    return row["status"], row["released_at"]


def test_release_boundary(conn):
    order_id = add_order(conn)
    assert release_due_orders(conn, RELEASE_AT - TINY) == []
    assert status_of(conn, order_id) == ("SCHEDULED", None)

    assert release_due_orders(conn, RELEASE_AT) == [order_id]
    assert status_of(conn, order_id) == ("PLACED", "2026-10-23T19:30:00.000000+00:00")


def test_released_at_is_the_run_time_not_release_at(conn):
    order_id = add_order(conn)
    late = RELEASE_AT + timedelta(minutes=7)
    release_due_orders(conn, late)
    assert status_of(conn, order_id) == ("PLACED", to_db(late))


def test_second_run_releases_nothing(conn):
    order_id = add_order(conn)
    assert release_due_orders(conn, RELEASE_AT) == [order_id]
    assert release_due_orders(conn, RELEASE_AT) == []
    assert release_due_orders(conn, RELEASE_AT + timedelta(hours=1)) == []
    assert status_of(conn, order_id) == ("PLACED", to_db(RELEASE_AT))


def test_catch_up_after_downtime(conn):
    ids = [add_order(conn, release_at=RELEASE_AT + timedelta(hours=h)) for h in range(3)]
    future = add_order(conn, release_at=RELEASE_AT + timedelta(days=1))
    assert release_due_orders(conn, RELEASE_AT + timedelta(hours=5)) == ids
    assert status_of(conn, future)[0] == "SCHEDULED"


@pytest.mark.parametrize("status", ["PLACED", "PREPARING", "CANCELLED"])
def test_orders_that_are_not_scheduled_are_untouched(conn, status):
    order_id = add_order(conn, status=status)  # has a release_at, but not SCHEDULED
    immediate = add_order(conn, status="PLACED", release_at=None)
    assert release_due_orders(conn, RELEASE_AT + timedelta(days=1)) == []
    assert status_of(conn, order_id) == (status, None)
    assert status_of(conn, immediate) == ("PLACED", None)


def test_parallel_release_is_exactly_once(db_path, conn):
    expected = [add_order(conn, release_at=RELEASE_AT - timedelta(minutes=i)) for i in range(40)]
    workers, results, errors = 8, [], []
    barrier = threading.Barrier(workers)

    def run():
        c = connect(db_path)
        try:
            barrier.wait()
            for _ in range(3):
                results.extend(release_due_orders(c, RELEASE_AT))
        except Exception as exc:  # collected and asserted below
            errors.append(exc)
        finally:
            c.close()

    threads = [threading.Thread(target=run) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert sorted(results) == sorted(expected)  # every id once: none missing, none twice
