"""Order placement, lookup and status updates."""

import sqlite3
from datetime import UTC, datetime

from minidash.errors import DomainError, NotFoundError
from minidash.repositories import orders as orders_repo
from minidash.repositories import restaurants as restaurants_repo
from minidash.schemas import OrderIn, OrderStatus


def place_order(conn: sqlite3.Connection, order: OrderIn) -> dict:
    if restaurants_repo.get_restaurant(conn, order.restaurant_id) is None:
        raise NotFoundError(
            "RESTAURANT_NOT_FOUND", f"Restaurant {order.restaurant_id} does not exist"
        )

    menu = {row["id"]: row for row in restaurants_repo.list_menu(conn, order.restaurant_id)}
    lines: list[tuple[int, int, int]] = []
    for item in order.items:
        menu_item = menu.get(item.menu_item_id)
        if menu_item is None:
            raise DomainError(
                "ITEM_NOT_ON_MENU",
                f"Menu item {item.menu_item_id} is not on restaurant {order.restaurant_id}'s menu",
            )
        lines.append((item.menu_item_id, item.quantity, menu_item["price_cents"]))

    total = sum(qty * price for _, qty, price in lines)
    with conn:
        order_id = orders_repo.insert_order(
            conn,
            restaurant_id=order.restaurant_id,
            status=OrderStatus.PLACED.value,
            total_cents=total,
            address=order.address,
            created_at=datetime.now(UTC).isoformat(),
            items=lines,
        )
    return get_order(conn, order_id)


def get_order(conn: sqlite3.Connection, order_id: int) -> dict:
    row = orders_repo.get_order(conn, order_id)
    if row is None:
        raise NotFoundError("ORDER_NOT_FOUND", f"Order {order_id} does not exist")
    items = [
        {
            "menu_item_id": it["menu_item_id"],
            "name": it["name"],
            "quantity": it["quantity"],
            "unit_price_cents": it["unit_price_cents"],
            "line_total_cents": it["quantity"] * it["unit_price_cents"],
        }
        for it in orders_repo.get_order_items(conn, order_id)
    ]
    return {**dict(row), "items": items}


def update_status(conn: sqlite3.Connection, order_id: int, status: OrderStatus) -> dict:
    if orders_repo.get_order(conn, order_id) is None:
        raise NotFoundError("ORDER_NOT_FOUND", f"Order {order_id} does not exist")
    with conn:
        orders_repo.update_status(conn, order_id, status.value)
    return get_order(conn, order_id)
