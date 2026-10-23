"""S9: PATCH /orders/{id}/status cannot bypass scheduling (AC-13)."""

from datetime import UTC, datetime

import pytest

from minidash.db import connect
from minidash.services.scheduling import release_due_orders

ORDER = {
    "restaurant_id": 1,
    "items": [{"menu_item_id": 1, "quantity": 1}],
    "address": "1 Main St",
}
SCHEDULED = {**ORDER, "scheduled_for": "2026-10-23T16:00:00-04:00"}
RELEASE_AT = datetime(2026, 10, 23, 19, 30, tzinfo=UTC)


def release(db_path):
    conn = connect(db_path)
    try:
        return release_due_orders(conn, RELEASE_AT)
    finally:
        conn.close()


@pytest.mark.parametrize("target", ["PLACED", "PREPARING", "DELIVERED", "CANCELLED"])
def test_patch_cannot_touch_a_scheduled_order(client, db_path, target):
    order_id = client.post("/orders", json=SCHEDULED).json()["id"]
    r = client.patch(f"/orders/{order_id}/status", json={"status": target})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ORDER_IS_SCHEDULED"
    assert client.get(f"/orders/{order_id}").json()["status"] == "SCHEDULED"
    # and the normal release still happens afterwards
    assert release(db_path) == [order_id]


def test_patch_cannot_set_scheduled(client, db_path):
    order_id = client.post("/orders", json=ORDER).json()["id"]
    r = client.patch(f"/orders/{order_id}/status", json={"status": "SCHEDULED"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "STATUS_NOT_SETTABLE"
    assert client.get(f"/orders/{order_id}").json()["status"] == "PLACED"


def test_released_order_can_be_patched_normally(client, db_path):
    order_id = client.post("/orders", json=SCHEDULED).json()["id"]
    release(db_path)
    r = client.patch(f"/orders/{order_id}/status", json={"status": "PREPARING"})
    assert r.status_code == 200 and r.json()["status"] == "PREPARING"


def test_patch_unknown_order_is_404(client):
    r = client.patch("/orders/404/status", json={"status": "READY"})
    assert r.status_code == 404


def test_patch_to_the_current_status_is_not_mistaken_for_scheduled(client):
    # rowcount must count a matched row even when the value does not change
    order_id = client.post("/orders", json=ORDER).json()["id"]
    r = client.patch(f"/orders/{order_id}/status", json={"status": "PLACED"})
    assert r.status_code == 200 and r.json()["status"] == "PLACED"
