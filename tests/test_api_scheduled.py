"""S5: scheduled placement over HTTP (AC-1 to AC-6, AC-15)."""

import pytest

from .conftest import START  # 2026-10-23 14:00 New York


def order(restaurant_id=1, items=None, **extra):
    return {
        "restaurant_id": restaurant_id,
        "items": items or [{"menu_item_id": 1, "quantity": 2}],
        "address": "1 Main St",
        **extra,
    }


def error_code(response):
    return response.json()["error"]["code"]


def test_scheduled_order_is_created_scheduled(client):
    r = client.post("/orders", json=order(scheduled_for="2026-10-23T16:00:00-04:00"))
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "SCHEDULED"
    assert body["scheduled_for"] == "2026-10-23T20:00:00.000000+00:00"
    assert body["release_at"] == "2026-10-23T19:30:00.000000+00:00"
    assert body["released_at"] is None
    assert body["total_cents"] == 2900
    assert client.get(f"/orders/{body['id']}").json() == body


def test_order_without_schedule_is_placed_immediately(client):
    body = client.post("/orders", json=order()).json()
    assert body["status"] == "PLACED"
    assert (body["scheduled_for"], body["release_at"]) == (None, None)


def test_utc_z_suffix_is_accepted(client):
    r = client.post("/orders", json=order(scheduled_for="2026-10-23T20:00:00Z"))
    assert r.status_code == 201 and r.json()["status"] == "SCHEDULED"


@pytest.mark.parametrize(
    "scheduled_for, code",
    [
        ("2026-10-23T16:00:00", "SCHEDULE_TIMEZONE_REQUIRED"),
        ("2026-10-23T14:44:59-04:00", "SCHEDULE_TOO_SOON"),
        ("2026-10-23T13:00:00-04:00", "SCHEDULE_TOO_SOON"),
        ("2026-10-30T14:00:00.000001-04:00", "SCHEDULE_TOO_FAR"),
    ],
)
def test_api_error_codes(client, scheduled_for, code):
    r = client.post("/orders", json=order(scheduled_for=scheduled_for))
    assert r.status_code == 422
    assert error_code(r) == code
    assert client.get("/orders/1").status_code == 404  # nothing was stored


def test_api_accepts_both_boundaries(client):
    assert (
        client.post("/orders", json=order(scheduled_for="2026-10-23T14:45:00-04:00")).json()[
            "status"
        ]
        == "SCHEDULED"
    )
    assert (
        client.post("/orders", json=order(scheduled_for="2026-10-30T14:00:00-04:00")).json()[
            "status"
        ]
        == "SCHEDULED"
    )


@pytest.mark.parametrize(
    "restaurant_id, items, scheduled_for",
    [
        (5, [{"menu_item_id": 13, "quantity": 1}], "2026-10-23T16:00:00-04:00"),  # opens 18:00
        (5, [{"menu_item_id": 13, "quantity": 1}], "2026-10-23T18:15:00-04:00"),  # release 17:45
        (1, None, "2026-10-23T22:15:00-04:00"),  # Pasta Palace closes 22:00
    ],
)
def test_api_rejects_closed_restaurant(client, restaurant_id, items, scheduled_for):
    r = client.post("/orders", json=order(restaurant_id, items, scheduled_for=scheduled_for))
    assert r.status_code == 422
    assert error_code(r) == "RESTAURANT_CLOSED"


def test_closed_message_shows_local_kitchen_window(client):
    r = client.post("/orders", json=order(scheduled_for="2026-10-23T22:15:00-04:00"))
    assert "21:45-22:15" in r.json()["error"]["message"]
    assert "America/New_York" in r.json()["error"]["message"]


def test_overnight_restaurant_accepts_delivery_after_midnight(client):
    r = client.post(
        "/orders",
        json=order(
            5, [{"menu_item_id": 14, "quantity": 1}], scheduled_for="2026-10-24T01:30:00-04:00"
        ),
    )
    assert r.status_code == 201 and r.json()["status"] == "SCHEDULED"


def test_delivery_exactly_at_closing_is_accepted(client):
    r = client.post("/orders", json=order(scheduled_for="2026-10-23T22:00:00-04:00"))
    assert r.status_code == 201


@pytest.mark.parametrize(
    "payload, status, code",
    [
        # unknown restaurant beats a bad schedule
        (order(99, scheduled_for="2026-10-23T16:00:00"), 404, "RESTAURANT_NOT_FOUND"),
        # item problem beats a bad schedule
        (
            order(
                1, [{"menu_item_id": 13, "quantity": 1}], scheduled_for="2026-10-23T14:10:00-04:00"
            ),
            422,
            "ITEM_NOT_ON_MENU",
        ),
        # too soon beats closed (Late Night Noodles is closed at 14:30 too)
        (
            order(
                5, [{"menu_item_id": 13, "quantity": 1}], scheduled_for="2026-10-23T14:30:00-04:00"
            ),
            422,
            "SCHEDULE_TOO_SOON",
        ),
    ],
)
def test_validation_order(client, payload, status, code):
    r = client.post("/orders", json=payload)
    assert (r.status_code, error_code(r)) == (status, code)


def test_start_constant_matches_scenario():
    # Guard for the hard-coded times above: they assume START is 14:00 in New York.
    assert START.isoformat() == "2026-10-23T18:00:00+00:00"
