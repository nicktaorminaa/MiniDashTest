"""Order placement, lookup and status updates."""

import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from minidash.errors import DomainError, NotFoundError
from minidash.repositories import orders as orders_repo
from minidash.repositories import restaurants as restaurants_repo
from minidash.schemas import OrderIn, OrderStatus
from minidash.services.scheduling import kitchen_open_for_window, validate_schedule
from minidash.timeutil import to_db


def place_order(
    conn: sqlite3.Connection, order: OrderIn, now: datetime, business_tz: ZoneInfo
) -> dict:
    """Place an order now, or hold it as SCHEDULED when scheduled_for is given.

    Checks run in the order documented in requirements.md: restaurant, items, then schedule.
    """
    restaurant = restaurants_repo.get_restaurant(conn, order.restaurant_id)
    if restaurant is None:
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

    status, scheduled_for, release_at = OrderStatus.PLACED, None, None
    if order.scheduled_for is not None:
        release_utc = validate_schedule(order.scheduled_for, now)
        if not kitchen_open_for_window(
            restaurant["opens_at"],
            restaurant["closes_at"],
            release_utc,
            order.scheduled_for,
            business_tz,
        ):
            window_start = release_utc.astimezone(business_tz).strftime("%H:%M")
            window_end = order.scheduled_for.astimezone(business_tz).strftime("%H:%M")
            raise DomainError(
                "RESTAURANT_CLOSED",
                f"{restaurant['name']} (open {restaurant['opens_at']}-{restaurant['closes_at']} "
                f"{business_tz.key}) is closed during the kitchen window "
                f"{window_start}-{window_end}",
            )
        status = OrderStatus.SCHEDULED
        scheduled_for, release_at = to_db(order.scheduled_for), to_db(release_utc)

    total = sum(qty * price for _, qty, price in lines)
    with conn:
        order_id = orders_repo.insert_order(
            conn,
            restaurant_id=order.restaurant_id,
            status=status.value,
            total_cents=total,
            address=order.address,
            created_at=to_db(now),
            items=lines,
            scheduled_for=scheduled_for,
            release_at=release_at,
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
