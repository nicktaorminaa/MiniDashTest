"""Restaurant and menu use cases."""

import sqlite3

from minidash.errors import NotFoundError
from minidash.repositories import restaurants as repo


def list_restaurants(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in repo.list_restaurants(conn)]


def get_menu(conn: sqlite3.Connection, restaurant_id: int) -> list[dict]:
    if repo.get_restaurant(conn, restaurant_id) is None:
        raise NotFoundError("RESTAURANT_NOT_FOUND", f"Restaurant {restaurant_id} does not exist")
    return [dict(r) for r in repo.list_menu(conn, restaurant_id)]
