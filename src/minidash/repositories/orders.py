"""Data access for orders and order items."""

import sqlite3

from minidash.schemas import OrderStatus


def insert_order(
    conn: sqlite3.Connection,
    *,
    restaurant_id: int,
    status: str,
    total_cents: int,
    address: str,
    created_at: str,
    items: list[tuple[int, int, int]],
    scheduled_for: str | None = None,
    release_at: str | None = None,
) -> int:
    """Insert an order and its items. `items` is (menu_item_id, quantity, unit_price_cents)."""
    cur = conn.execute(
        "INSERT INTO orders (restaurant_id, status, total_cents, address, created_at, "
        "scheduled_for, release_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (restaurant_id, status, total_cents, address, created_at, scheduled_for, release_at),
    )
    order_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price_cents) "
        "VALUES (?, ?, ?, ?)",
        [(order_id, mid, qty, price) for mid, qty, price in items],
    )
    return order_id


def get_order(conn: sqlite3.Connection, order_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()


def get_order_items(conn: sqlite3.Connection, order_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT oi.menu_item_id, mi.name, oi.quantity, oi.unit_price_cents "
        "FROM order_items oi JOIN menu_items mi ON mi.id = oi.menu_item_id "
        "WHERE oi.order_id = ? ORDER BY oi.id",
        (order_id,),
    ).fetchall()


def update_status(conn: sqlite3.Connection, order_id: int, status: str) -> None:
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))


def release_due(conn: sqlite3.Connection, now_db: str) -> list[int]:
    """Move every SCHEDULED order with release_at <= now to PLACED. Returns the ids changed.

    The status check is in the WHERE clause, so an order already released or cancelled is never
    touched again, however many times or from however many connections this runs.
    """
    rows = conn.execute(
        "UPDATE orders SET status = ?, released_at = ? "
        "WHERE status = ? AND release_at <= ? RETURNING id",
        (OrderStatus.PLACED.value, now_db, OrderStatus.SCHEDULED.value, now_db),
    ).fetchall()
    return sorted(row["id"] for row in rows)
