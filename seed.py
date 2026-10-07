from database import get_db, init_db

init_db()

menu = [
    ("Chicken & Chips", "Crispy chicken served with chips", 50.00),
    ("Beef Burger", "Beef burger with fresh toppings", 45.00),
    ("Chicken Burger", "Chicken burger with fresh toppings", 45.00),
    ("Large Chips", "Crispy golden chips", 25.00),
    ("Soft Drink", "Assorted soft drink", 15.00),
]

conn = get_db()

for name, description, price in menu:
    exists = conn.execute(
        "SELECT id FROM menu_items WHERE name = ?",
        (name,)
    ).fetchone()

    if not exists:
        conn.execute(
            """
            INSERT INTO menu_items
            (name, description, price)
            VALUES (?, ?, ?)
            """,
            (name, description, price)
        )

conn.commit()
conn.close()

print("Paradise menu loaded successfully.")
