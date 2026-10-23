"""SQLite connection, schema and seed data."""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS restaurants (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    cuisine TEXT NOT NULL,
    opens_at TEXT NOT NULL,       -- local time "HH:MM"
    closes_at TEXT NOT NULL,      -- local time "HH:MM"
    avg_prep_minutes INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS menu_items (
    id INTEGER PRIMARY KEY,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id),
    name TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id),
    status TEXT NOT NULL,
    total_cents INTEGER NOT NULL,
    address TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    menu_item_id INTEGER NOT NULL REFERENCES menu_items(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents INTEGER NOT NULL
);
"""

RESTAURANTS = [
    (1, "Pasta Palace", "Italian", "11:00", "22:00", 20),
    (2, "Sushi Wave", "Japanese", "12:00", "21:30", 25),
    (3, "Taco Town", "Mexican", "10:00", "23:00", 15),
    (4, "Curry House", "Indian", "11:30", "22:30", 30),
    (5, "Late Night Noodles", "Chinese", "18:00", "02:00", 18),
]

MENU_ITEMS = [
    (1, 1, "Spaghetti Carbonara", 1450),
    (2, 1, "Margherita Pizza", 1300),
    (3, 1, "Tiramisu", 750),
    (4, 2, "Salmon Nigiri (2 pc)", 650),
    (5, 2, "California Roll", 900),
    (6, 2, "Miso Soup", 400),
    (7, 3, "Carnitas Taco", 450),
    (8, 3, "Chicken Burrito", 1100),
    (9, 3, "Chips and Guacamole", 600),
    (10, 4, "Chicken Tikka Masala", 1550),
    (11, 4, "Garlic Naan", 350),
    (12, 4, "Vegetable Samosa (2 pc)", 550),
    (13, 5, "Dan Dan Noodles", 1250),
    (14, 5, "Pork Dumplings (6 pc)", 900),
    (15, 5, "Scallion Pancake", 650),
]


def connect(db_path: str) -> sqlite3.Connection:
    """Open a connection that returns rows as dict-like objects."""
    conn = sqlite3.connect(db_path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Columns added after the baseline. New and existing databases both get them through
# migrate(), so there is one code path for both.
SCHEDULE_COLUMNS = ("scheduled_for", "release_at", "released_at")


def migrate(conn: sqlite3.Connection) -> None:
    """Add the scheduled-order columns and index if they are missing. Safe to run repeatedly."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(orders)")}
    for column in SCHEDULE_COLUMNS:
        if column not in existing:
            conn.execute(f"ALTER TABLE orders ADD COLUMN {column} TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_orders_status_release ON orders(status, release_at)"
    )


def init_db(db_path: str, seed: bool = True) -> None:
    """Create tables, apply migrations and, if the database is empty, insert seed data."""
    conn = connect(db_path)
    try:
        with conn:
            conn.executescript(SCHEMA)
            migrate(conn)
            if seed and conn.execute("SELECT COUNT(*) FROM restaurants").fetchone()[0] == 0:
                conn.executemany("INSERT INTO restaurants VALUES (?, ?, ?, ?, ?, ?)", RESTAURANTS)
                conn.executemany("INSERT INTO menu_items VALUES (?, ?, ?, ?)", MENU_ITEMS)
    finally:
        conn.close()
