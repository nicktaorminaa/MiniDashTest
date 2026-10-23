"""Tests for the five baseline endpoints."""

ORDER = {
    "restaurant_id": 1,
    "items": [{"menu_item_id": 1, "quantity": 2}, {"menu_item_id": 3, "quantity": 1}],
    "address": "1 Main St",
}


def test_list_restaurants_returns_seeded_five(client):
    r = client.get("/restaurants")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 5
    assert set(body[0]) == {"id", "name", "cuisine", "opens_at", "closes_at", "avg_prep_minutes"}


def test_menu_for_restaurant(client):
    r = client.get("/restaurants/2/menu")
    assert r.status_code == 200
    assert [m["name"] for m in r.json()] == ["Salmon Nigiri (2 pc)", "California Roll", "Miso Soup"]


def test_menu_unknown_restaurant_is_404(client):
    r = client.get("/restaurants/999/menu")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "RESTAURANT_NOT_FOUND"


def test_place_order_computes_total_and_is_placed(client):
    r = client.post("/orders", json=ORDER)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "PLACED"
    assert body["total_cents"] == 2 * 1450 + 750
    assert [i["line_total_cents"] for i in body["items"]] == [2900, 750]


def test_place_order_rejects_item_from_another_restaurant(client):
    bad = {**ORDER, "items": [{"menu_item_id": 4, "quantity": 1}]}
    r = client.post("/orders", json=bad)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ITEM_NOT_ON_MENU"


def test_place_order_rejects_empty_items_and_zero_quantity(client):
    assert client.post("/orders", json={**ORDER, "items": []}).status_code == 422
    zero = {**ORDER, "items": [{"menu_item_id": 1, "quantity": 0}]}
    assert client.post("/orders", json=zero).status_code == 422


def test_place_order_unknown_restaurant_is_404(client):
    r = client.post("/orders", json={**ORDER, "restaurant_id": 42})
    assert r.status_code == 404


def test_get_order_round_trip(client):
    created = client.post("/orders", json=ORDER).json()
    r = client.get(f"/orders/{created['id']}")
    assert r.status_code == 200
    assert r.json() == created


def test_get_unknown_order_is_404(client):
    r = client.get("/orders/12345")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ORDER_NOT_FOUND"


def test_patch_status(client):
    created = client.post("/orders", json=ORDER).json()
    r = client.patch(f"/orders/{created['id']}/status", json={"status": "PREPARING"})
    assert r.status_code == 200
    assert r.json()["status"] == "PREPARING"


def test_patch_status_rejects_unknown_value(client):
    created = client.post("/orders", json=ORDER).json()
    r = client.patch(f"/orders/{created['id']}/status", json={"status": "TELEPORTED"})
    assert r.status_code == 422
