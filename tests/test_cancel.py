"""S8: cancelling a scheduled order before it is released (AC-11, AC-11a, AC-12)."""

import threading
import time
from datetime import UTC, datetime, timedelta

from minidash.db import connect
from minidash.services.scheduling import release_due_orders

ORDER = {
    "restaurant_id": 1,
    "items": [{"menu_item_id": 1, "quantity": 1}],
    "address": "1 Main St",
    "scheduled_for": "2026-10-23T16:00:00-04:00",
}
RELEASE_AT = datetime(2026, 10, 23, 19, 30, tzinfo=UTC)


def release(db_path, now):
    conn = connect(db_path)
    try:
        return release_due_orders(conn, now)
    finally:
        conn.close()


def test_cancelled_order_is_never_released(client, db_path):
    order_id = client.post("/orders", json=ORDER).json()["id"]
    r = client.post(f"/orders/{order_id}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"

    assert release(db_path, RELEASE_AT + timedelta(days=1)) == []
    body = client.get(f"/orders/{order_id}").json()
    assert (body["status"], body["released_at"]) == ("CANCELLED", None)


def test_cancel_after_release_is_409_and_changes_nothing(client, db_path):
    order_id = client.post("/orders", json=ORDER).json()["id"]
    assert release(db_path, RELEASE_AT) == [order_id]

    r = client.post(f"/orders/{order_id}/cancel")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ORDER_NOT_CANCELLABLE"
    assert client.get(f"/orders/{order_id}").json()["status"] == "PLACED"


def test_cancel_twice_is_409(client):
    order_id = client.post("/orders", json=ORDER).json()["id"]
    assert client.post(f"/orders/{order_id}/cancel").status_code == 200
    r = client.post(f"/orders/{order_id}/cancel")
    assert r.status_code == 409 and "CANCELLED" in r.json()["error"]["message"]


def test_immediate_order_cannot_be_cancelled_here(client):
    order = {k: v for k, v in ORDER.items() if k != "scheduled_for"}
    order_id = client.post("/orders", json=order).json()["id"]
    assert client.post(f"/orders/{order_id}/cancel").status_code == 409
    assert client.get(f"/orders/{order_id}").json()["status"] == "PLACED"


def test_cancel_unknown_order_is_404(client):
    r = client.post("/orders/777/cancel")
    assert r.status_code == 404 and r.json()["error"]["code"] == "ORDER_NOT_FOUND"


def test_due_but_not_yet_released_can_still_be_cancelled(client, clock):
    order_id = client.post("/orders", json=ORDER).json()["id"]
    clock.set(RELEASE_AT + timedelta(seconds=10))  # due, but the release job has not run
    assert client.post(f"/orders/{order_id}/cancel").json()["status"] == "CANCELLED"


def test_cancel_racing_release_never_does_both(client, db_path):
    # Order i is due at RELEASE_AT + i minutes. The releaser walks time forward while the
    # canceller works from the last order backwards, so they meet part-way and both outcomes
    # happen in one run.
    ids = []
    for i in range(40):
        delivery = datetime(2026, 10, 23, 20, 0, tzinfo=UTC) + timedelta(minutes=i)
        ids.append(
            client.post("/orders", json={**ORDER, "scheduled_for": delivery.isoformat()}).json()[
                "id"
            ]
        )
    released, cancelled = [], []
    barrier = threading.Barrier(2)

    def releaser():
        barrier.wait()
        for i in range(40):
            released.extend(release(db_path, RELEASE_AT + timedelta(minutes=i)))
            time.sleep(0.002)

    def canceller():
        barrier.wait()
        for order_id in reversed(ids):
            if client.post(f"/orders/{order_id}/cancel").status_code == 200:
                cancelled.append(order_id)

    threads = [threading.Thread(target=releaser), threading.Thread(target=canceller)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert released and cancelled  # the race really happened
    assert sorted(released + cancelled) == ids  # each order exactly one outcome
    for order_id in ids:
        body = client.get(f"/orders/{order_id}").json()
        if order_id in cancelled:
            assert (body["status"], body["released_at"]) == ("CANCELLED", None)
        else:
            assert body["status"] == "PLACED" and body["released_at"] is not None
