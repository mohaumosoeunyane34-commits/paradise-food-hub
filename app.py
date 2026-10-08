import os
import sqlite3
from functools import wraps

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    redirect,
    session,
    url_for
)

from database import get_db, init_db


app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "paradise-food-hub-change-this-secret"
)

init_db()


def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        return function(*args, **kwargs)

    return wrapper


def calculate_cart(conn, cart_items):
    if not isinstance(cart_items, list) or not cart_items:
        raise ValueError("Cart is empty.")

    items = []
    total = 0.0

    for cart_item in cart_items:
        try:
            item_id = int(cart_item.get("id"))
            quantity = int(cart_item.get("quantity", 1))
        except (TypeError, ValueError, AttributeError):
            raise ValueError("Invalid cart item.")

        if quantity < 1 or quantity > 99:
            raise ValueError("Invalid quantity.")

        row = conn.execute(
            """
            SELECT id, name, description, price, available
            FROM menu_items
            WHERE id = ?
            """,
            (item_id,)
        ).fetchone()

        if not row:
            raise ValueError(f"Menu item {item_id} not found.")

        if not row["available"]:
            raise ValueError(f"{row['name']} is unavailable.")

        price = float(row["price"])
        line_total = price * quantity
        total += line_total

        items.append({
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "price": price,
            "quantity": quantity,
            "line_total": line_total
        })

    return items, round(total, 2)


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/checkout")
def checkout():
    return render_template("checkout.html")


@app.get("/receipt/<int:order_id>")
def receipt(order_id):
    return render_template(
        "receipt.html",
        order_id=order_id
    )


@app.get("/admin")
def admin():
    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    return render_template("admin.html")


@app.get("/login")
def login():
    return render_template("login.html")


@app.post("/login")
def login_post():
    data = request.form

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    admin_username = os.environ.get(
        "ADMIN_USERNAME",
        "admin"
    )

    admin_password = os.environ.get(
        "ADMIN_PASSWORD",
        "paradise34"
    )

    if (
        username == admin_username
        and password == admin_password
    ):
        session["admin_logged_in"] = True
        return redirect(url_for("admin"))

    return render_template(
        "login.html",
        error="Invalid username or password."
    ), 401


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/api/menu")
def api_menu():
    conn = get_db()

    rows = conn.execute(
        """
        SELECT id, name, description, price, available
        FROM menu_items
        WHERE available = 1
        ORDER BY id
        """
    ).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


@app.post("/api/order-preview")
def order_preview():
    data = request.get_json(silent=True) or {}

    conn = get_db()

    try:
        items, total = calculate_cart(
            conn,
            data.get("items", [])
        )

        return jsonify({
            "success": True,
            "items": items,
            "total": total
        })

    except ValueError as error:
        return jsonify({
            "error": str(error)
        }), 400

    finally:
        conn.close()


@app.post("/api/orders")
def create_order():

    data = request.get_json(silent=True) or {}

    customer_name = str(
        data.get("customer_name", "")
    ).strip()

    phone = str(
        data.get("phone", "")
    ).strip()

    order_type = str(
        data.get("order_type", "DELIVERY")
    ).strip().upper()

    address = str(
        data.get("address", "")
    ).strip()

    notes = str(
        data.get("notes", "")
    ).strip()

    payment_method = str(
        data.get("payment_method", "CASH")
    ).strip().upper()

    if not customer_name or not phone:
        return jsonify({
            "error": "Name and phone are required."
        }), 400

    if order_type not in {
        "PICKUP",
        "DELIVERY"
    }:
        return jsonify({
            "error": "Order type must be PICKUP or DELIVERY."
        }), 400

    if (
        order_type == "DELIVERY"
        and not address
    ):
        return jsonify({
            "error": "Delivery address is required."
        }), 400

    allowed_payment_methods = {
        "CASH",
        "MOPAY"
    }

    if payment_method not in allowed_payment_methods:
        return jsonify({
            "error": "Invalid payment method."
        }), 400

    conn = get_db()

    try:
        items, total = calculate_cart(
            conn,
            data.get("items", [])
        )

        payment_status = "UNPAID"

        cursor = conn.execute(
            """
            INSERT INTO orders
            (
                customer_name,
                phone,
                address,
                order_type,
                notes,
                payment_method,
                payment_status,
                total,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer_name,
                phone,
                address if order_type == "DELIVERY" else "",
                order_type,
                notes,
                payment_method,
                payment_status,
                total,
                "PENDING"
            )
        )

        order_id = cursor.lastrowid

        for item in items:
            conn.execute(
                """
                INSERT INTO order_items
                (
                    order_id,
                    menu_item_id,
                    quantity,
                    price
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    order_id,
                    item["id"],
                    item["quantity"],
                    item["price"]
                )
            )

        conn.commit()

        return jsonify({
            "success": True,
            "order_id": order_id,
            "status": "PENDING",
            "payment_status": payment_status,
            "total": total
        }), 201

    except ValueError as error:
        conn.rollback()

        return jsonify({
            "error": str(error)
        }), 400

    except Exception:
        conn.rollback()

        return jsonify({
            "error": "Unable to create order."
        }), 500

    finally:
        conn.close()


@app.get("/api/orders/<int:order_id>")
def get_order(order_id):

    conn = get_db()

    try:
        order = conn.execute(
            """
            SELECT
                id,
                customer_name,
                phone,
                address,
                order_type,
                notes,
                payment_method,
                payment_status,
                total,
                status,
                created_at
            FROM orders
            WHERE id = ?
            """,
            (order_id,)
        ).fetchone()

        if not order:
            return jsonify({
                "error": "Order not found."
            }), 404

        items = conn.execute(
            """
            SELECT
                oi.menu_item_id AS id,
                m.name,
                oi.quantity,
                oi.price
            FROM order_items oi
            LEFT JOIN menu_items m
                ON m.id = oi.menu_item_id
            WHERE oi.order_id = ?
            """,
            (order_id,)
        ).fetchall()

        return jsonify({
            "order": dict(order),
            "items": [
                dict(item)
                for item in items
            ]
        })

    finally:
        conn.close()


@app.get("/orders")
@admin_required
def orders():

    conn = get_db()

    try:
        rows = conn.execute(
            """
            SELECT
                id,
                customer_name,
                phone,
                address,
                order_type,
                notes,
                payment_method,
                payment_status,
                total,
                status,
                created_at
            FROM orders
            ORDER BY id DESC
            """
        ).fetchall()

        return jsonify([
            dict(row)
            for row in rows
        ])

    finally:
        conn.close()


@app.patch("/api/orders/<int:order_id>/status")
@admin_required
def update_order_status(order_id):

    data = request.get_json(silent=True) or {}

    status = str(
        data.get("status", "")
    ).upper()

    allowed = {
        "PENDING",
        "ACCEPTED",
        "PREPARING",
        "READY",
        "DELIVERED",
        "CANCELLED"
    }

    if status not in allowed:
        return jsonify({
            "error": "Invalid order status."
        }), 400

    conn = get_db()

    try:
        cursor = conn.execute(
            """
            UPDATE orders
            SET status = ?
            WHERE id = ?
            """,
            (
                status,
                order_id
            )
        )

        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({
                "error": "Order not found."
            }), 404

        return jsonify({
            "success": True,
            "order_id": order_id,
            "status": status
        })

    finally:
        conn.close()


@app.get("/health")
def health():
    return jsonify({
        "status": "ONLINE",
        "service": "Paradise Food Hub"
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=False
    )
