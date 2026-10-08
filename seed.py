from database import get_db, init_db

init_db()

menu = [
    # KOTA
    ("Jumanji", "Polony, chips, lettuce, egg + vienna", 35),
    ("Cloud 9", "Chips, polony, veggies, cheese, Russian + cheese griller", 50),
    ("Weekend Feast", "Chips, veggies, polony, cheese, ham, onion rings + Russian + beef patty", 68),
    ("Heaven's Bite", "Vienna, cheese, cheese griller, veggies, chips, sunny side up, Russian, egg, patty, ham, onion + BBQ sauce", 110),
    ("Blue Monday", "Ribs, lettuce, fries, onion, vienna x2, cheese x2, ham, patty, Russian, sunny side up, cheese griller x3, BBQ sauce + 300ML juice", 130),
    ("Table Mountain", "Vienna x3, fries, veggies, Russian, beef patty, ribs, ham x3, cheese griller x3, BBQ sauce, sunny side up x3 + side chips + 1L Coke", 167),

    # CHIPS
    ("Chips - Small", "Small portion", 25),
    ("Chips - Medium", "Medium portion", 35),
    ("Chips - Large", "Large portion", 45),
    ("Chips - X-Large", "Extra large portion", 60),

    # DRINKS
    ("300ML Drink", "300ML drink", 15),
    ("1L Drink", "1 litre drink", 20),
    ("2L Drink", "2 litre drink", 30),
    ("2L Coke", "2 litre Coke", 15),

    # RUSSIANS
    ("Smoked Russian - Small", "Small smoked Russian", 15),
    ("Smoked Russian - Large", "Large smoked Russian", 25),

    # DAGWOOD
    ("Dagwood - Without Juice", "Veggies, polony, beef patty, sunny side up, side chips, vienna", 80),
    ("Dagwood - With Juice", "Veggies, polony, beef patty, sunny side up, side chips, vienna + juice", 95),

    # LOADED FRIES
    ("Loaded Fries", "Patty, cheese, onion, cheese griller x2, sunny side up, smoked Russian + chef sauce", 120),
]

conn = get_db()

# Clear temporary/old menu items
conn.execute("DELETE FROM menu_items")

for name, description, price in menu:
    conn.execute("""
        INSERT INTO menu_items
        (name, description, price, available)
        VALUES (?, ?, ?, 1)
    """, (name, description, price))

conn.commit()
conn.close()

print(f"Paradise Food Hub menu loaded successfully: {len(menu)} items.")
