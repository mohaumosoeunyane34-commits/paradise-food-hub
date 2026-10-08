import os

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    session,
    redirect,
    url_for
)

from werkzeug.security import check_password_hash

from database import get_db, init_db


app = Flask(__name__)

app.secret_key = os.environ.get(
    "PARADISE_SECRET_KEY",
    "development-only-secret"
)

ADMIN_USERNAME = "admin"

ADMIN_PASSWORD_HASH = "scrypt:32768:8:1$AONpj7EANrwN3VvN$a3d06e3bc766caeaa560a69141fd21ffe9b876c82549a4412cc7af3faf312aea1f265313f85c8025e28924c6ef5945cf71c4101ea6043735a016a39cd577fafe"

init_db()


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

@app.get("/api/status")
def status():
    return jsonify({
        "project": "Paradise Food Hub",
        "status": "ONLINE",
        "version": "1.0.0"
    })


@app.get("/menu")
def menu():
    conn = get_db()

    rows = conn.execute("""
        SELECT id, name, description, price, available
        FROM menu_items
        WHERE available = 1
        ORDER BY id
    """).fetchall()

    conn.close()

    return jsonify([dict(row) for row in rows])


def calculate_cart(conn, items):

    if not isinstance(items, list) or not items:
        raise ValueError("Cart is empty.")

    result = []
    total = 0.0

    for item in items:

        try:
            item_id = int(item["id"])
            quantity = int(item["quantity"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Invalid cart item.")

        if quantity < 1 or quantity > 100:
            raise ValueError("Invalid quantity.")

        row = conn.execute("""
            SELECT id, name, price
            FROM menu_items
            WHERE id = ? AND available = 1
        """, (item_id,)).fetchone()

        if not row:
            raise ValueError(
                f"Menu item {item_id} is unavailable."
            )

        subtotal = float(row["price"]) * quantity

        total += subtotal

        result.append({
            "id": row["id"],
            "name": row["name"],
            "price": float(row["price"]),
            "quantity": quantity,
            "subtotal": subtotal
        })

    return result, total


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

    if order_type not in {"PICKUP", "DELIVERY"}:
        return jsonify({
            "error": "Order type must be PICKUP or DELIVERY."
        }), 400

    if order_type == "DELIVERY" and not address:
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

        cursor = conn.execute("""
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
        """, (
            customer_name,
            phone,
            address if order_type == "DELIVERY" else "",
            order_type,
            notes,
            payment_method,
            payment_status,
            total,
            "PENDING"
        ))

        order_id = cursor.lastrowid

        for item in items:

            conn.execute("""
                INSERT INTO order_items
                (order_id, menu_item_id, quantity, price)
                VALUES (?, ?, ?, ?)
            """, (
                order_id,
                item["id"],
                item["quantity"],
                item["price"]
            ))

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

    order = conn.execute("""
        SELECT id, customer_name, phone, address,
               total, status, created_at
        FROM orders
        WHERE id = ?
    """, (order_id,)).fetchone()

    if not order:

        conn.close()

        return jsonify({
            "error": "Order not found."
        }), 404

    items = conn.execute("""
        SELECT
            oi.menu_item_id AS id,
            mi.name,
            oi.quantity,
            oi.price,
            (oi.quantity * oi.price) AS subtotal
        FROM order_items oi
        JOIN menu_items mi
            ON mi.id = oi.menu_item_id
        WHERE oi.order_id = ?
        ORDER BY oi.id
    """, (order_id,)).fetchall()

    conn.close()

    return jsonify({
        "order": dict(order),
        "items": [dict(item) for item in items]
    })


@app.get("/orders")
def orders():

    if not session.get("admin_logged_in"):

        return jsonify({
            "error": "Unauthorized"
        }), 401

    conn = get_db()

    rows = conn.execute("""
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
    """).fetchall()

    conn.close()

    return jsonify([dict(row) for row in rows])


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        )

        password = request.form.get(
            "password",
            ""
        )

        if (
            username == ADMIN_USERNAME
            and check_password_hash(
                ADMIN_PASSWORD_HASH,
                password
            )
        ):

            session["admin_logged_in"] = True

            return redirect(
                url_for("admin")
            )

        return render_template(
            "login.html",
            error="Invalid username or password."
        )

    return render_template("login.html")


@app.get("/admin")
def admin():

    if not session.get("admin_logged_in"):

        return redirect(
            url_for("login")
        )

    return render_template("admin.html")


@app.get("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


@app.patch("/api/orders/<int:order_id>/status")
def update_order_status(order_id):

    if not session.get("admin_logged_in"):

        return jsonify({
            "error": "Unauthorized"
        }), 401

    data = request.get_json(
        silent=True
    ) or {}

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

    cursor = conn.execute("""
        UPDATE orders
        SET status = ?
        WHERE id = ?
    """, (
        status,
        order_id
    ))

    conn.commit()

    changed = cursor.rowcount

    conn.close()

    if not changed:

        return jsonify({
            "error": "Order not found."
        }), 404

    return jsonify({
        "success": True,
        "order_id": order_id,
        "status": status
    })


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
