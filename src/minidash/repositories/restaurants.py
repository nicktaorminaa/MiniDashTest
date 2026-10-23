"""Data access for restaurants and menu items."""

import sqlite3


def list_restaurants(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM restaurants ORDER BY id").fetchall()


def get_restaurant(conn: sqlite3.Connection, restaurant_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM restaurants WHERE id = ?", (restaurant_id,)).fetchone()


def list_menu(conn: sqlite3.Connection, restaurant_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, name, price_cents FROM menu_items WHERE restaurant_id = ? ORDER BY id",
        (restaurant_id,),
    ).fetchall()
