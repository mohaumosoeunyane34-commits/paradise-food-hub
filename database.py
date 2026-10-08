import sqlite3
from pathlib import Path

DB_PATH = Path("data/paradise.db")


def get_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            available INTEGER DEFAULT 1
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT,
            order_type TEXT DEFAULT 'DELIVERY',
            notes TEXT,
            payment_method TEXT DEFAULT 'CASH',
            payment_status TEXT DEFAULT 'UNPAID',
            total REAL NOT NULL,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            menu_item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(menu_item_id) REFERENCES menu_items(id)
        )
    """)

    # Add new columns to older databases
    columns = {
        "address": "TEXT",
        "order_type": "TEXT DEFAULT 'DELIVERY'",
        "notes": "TEXT",
        "payment_method": "TEXT DEFAULT 'CASH'",
        "payment_status": "TEXT DEFAULT 'UNPAID'"
    }

    existing_columns = {
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(orders)"
        ).fetchall()
    }

    for column, definition in columns.items():
        if column not in existing_columns:
            conn.execute(
                f"ALTER TABLE orders ADD COLUMN {column} {definition}"
            )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Paradise Food Hub database initialized.")
