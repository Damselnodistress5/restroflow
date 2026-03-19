import json
import os
import sqlite3
import time
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "restroflow.sqlite3"


def hash_password(raw: str) -> str:
    return sha256(raw.encode("utf-8")).hexdigest()


def now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def code(prefix: str) -> str:
    return f"{prefix}{int(time.time() * 1000)}"


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
          user_id INTEGER PRIMARY KEY AUTOINCREMENT,
          full_name TEXT NOT NULL,
          email TEXT NOT NULL UNIQUE,
          phone TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'customer',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS dining_tables (
          table_id INTEGER PRIMARY KEY AUTOINCREMENT,
          table_code TEXT NOT NULL UNIQUE,
          capacity INTEGER NOT NULL DEFAULT 4,
          area TEXT NOT NULL DEFAULT 'indoor',
          status TEXT NOT NULL DEFAULT 'available'
        );

        CREATE TABLE IF NOT EXISTS menu_categories (
          category_id INTEGER PRIMARY KEY AUTOINCREMENT,
          category_name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS menu_items (
          item_id INTEGER PRIMARY KEY AUTOINCREMENT,
          category_id INTEGER NOT NULL,
          item_code TEXT NOT NULL UNIQUE,
          item_name TEXT NOT NULL,
          price REAL NOT NULL DEFAULT 0,
          is_veg INTEGER NOT NULL DEFAULT 1,
          is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS coupons (
          coupon_id INTEGER PRIMARY KEY AUTOINCREMENT,
          coupon_code TEXT NOT NULL UNIQUE,
          discount_percent REAL NOT NULL,
          is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS orders (
          order_id INTEGER PRIMARY KEY AUTOINCREMENT,
          order_code TEXT NOT NULL UNIQUE,
          user_id INTEGER,
          table_id INTEGER,
          order_notes TEXT,
          status TEXT NOT NULL DEFAULT 'pending',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS order_items (
          order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
          order_id INTEGER NOT NULL,
          item_id INTEGER NOT NULL,
          quantity INTEGER NOT NULL,
          unit_price REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS payments (
          payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
          order_id INTEGER NOT NULL UNIQUE,
          subtotal REAL NOT NULL,
          discount_amount REAL NOT NULL DEFAULT 0,
          cgst_amount REAL NOT NULL DEFAULT 0,
          sgst_amount REAL NOT NULL DEFAULT 0,
          grand_total REAL NOT NULL,
          payment_method TEXT NOT NULL,
          payment_status TEXT NOT NULL DEFAULT 'paid',
          paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS feedback (
          feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
          order_id INTEGER,
          user_id INTEGER,
          food_rating INTEGER NOT NULL,
          service_rating INTEGER NOT NULL,
          comments TEXT,
          submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS support_queries (
          query_id INTEGER PRIMARY KEY AUTOINCREMENT,
          query_code TEXT NOT NULL UNIQUE,
          full_name TEXT NOT NULL,
          contact_number TEXT NOT NULL,
          order_code TEXT,
          issue_type TEXT NOT NULL,
          description TEXT NOT NULL,
          photo_filename TEXT,
          status TEXT NOT NULL DEFAULT 'pending',
          submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS contact_messages (
          message_id INTEGER PRIMARY KEY AUTOINCREMENT,
          message_code TEXT NOT NULL UNIQUE,
          full_name TEXT NOT NULL,
          email TEXT NOT NULL,
          phone TEXT,
          category TEXT NOT NULL,
          message_text TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute("INSERT OR IGNORE INTO coupons (coupon_code, discount_percent, is_active) VALUES ('SAVE10', 10, 1)")
    cur.execute("INSERT OR IGNORE INTO menu_categories (category_name) VALUES ('Uncategorized')")
    conn.commit()
    conn.close()


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return {}

    def _serve_file(self, path: Path):
        if not path.exists() or not path.is_file():
            self.send_error(404, "Not Found")
            return
        ctype = "text/plain; charset=utf-8"
        suffix = path.suffix.lower()
        if suffix in [".html", ".htm"]:
            ctype = "text/html; charset=utf-8"
        elif suffix == ".css":
            ctype = "text/css; charset=utf-8"
        elif suffix == ".js":
            ctype = "application/javascript; charset=utf-8"

        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._serve_file(BASE_DIR / "home_page.html")
            return

        if path == "/api/orders.php":
            action = (qs.get("action", [""])[0]).strip()
            if action != "bill":
                self._json(404, {"ok": False, "message": "Unknown action"})
                return
            order_code = (qs.get("order_code", [""])[0]).strip()
            if not order_code:
                self._json(400, {"ok": False, "message": "order_code is required"})
                return
            conn = db_conn()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT o.order_id, o.order_code, o.created_at, o.status,
                       COALESCE(t.table_code, 'Takeaway') AS table_name,
                       mi.item_name, oi.quantity, oi.unit_price,
                       (oi.quantity * oi.unit_price) AS line_total
                FROM orders o
                LEFT JOIN dining_tables t ON t.table_id = o.table_id
                JOIN order_items oi ON oi.order_id = o.order_id
                JOIN menu_items mi ON mi.item_id = oi.item_id
                WHERE o.order_code = ?
                """,
                (order_code,),
            )
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            if not rows:
                self._json(404, {"ok": False, "message": "Order not found"})
            else:
                self._json(200, {"ok": True, "bill": rows})
            return

        if path == "/api/admin/sales.php":
            conn = db_conn()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT o.order_code, o.created_at, COALESCE(t.table_code, 'Takeaway') AS table_name,
                       p.grand_total, p.payment_method,
                       u.full_name AS customer_name, u.email AS customer_email, u.phone AS customer_phone
                FROM payments p
                JOIN orders o ON o.order_id = p.order_id
                LEFT JOIN dining_tables t ON t.table_id = o.table_id
                LEFT JOIN users u ON u.user_id = o.user_id
                ORDER BY p.paid_at DESC, p.payment_id DESC
                """
            )
            rows = [
                {
                    "order_id": r["order_code"],
                    "date": r["created_at"],
                    "table_name": r["table_name"],
                    "grand_total": float(r["grand_total"] or 0),
                    "payment_method": r["payment_method"],
                    "customer_name": r["customer_name"] or "",
                    "customer_email": r["customer_email"] or "",
                    "customer_phone": r["customer_phone"] or "",
                }
                for r in cur.fetchall()
            ]
            conn.close()
            self._json(200, {"ok": True, "orders": rows})
            return

        if path == "/api/admin/feedback.php":
            conn = db_conn()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT f.feedback_id, f.food_rating, f.service_rating, f.comments, f.submitted_at,
                       COALESCE(t.table_code, 'Takeaway') AS table_name,
                       u.full_name AS customer_name, u.email AS customer_email, u.phone AS customer_phone
                FROM feedback f
                LEFT JOIN orders o ON o.order_id = f.order_id
                LEFT JOIN dining_tables t ON t.table_id = o.table_id
                LEFT JOIN users u ON u.user_id = COALESCE(f.user_id, o.user_id)
                ORDER BY f.submitted_at DESC, f.feedback_id DESC
                """
            )
            rows = []
            for r in cur.fetchall():
                food = int(r["food_rating"] or 0)
                service = int(r["service_rating"] or 0)
                avg = round((food + service) / 2) if (food or service) else 0
                rows.append(
                    {
                        "feedback_id": r["feedback_id"],
                        "table_name": r["table_name"],
                        "food_rating": food,
                        "service_rating": service,
                        "star_rating": avg,
                        "comment": r["comments"] or "",
                        "date": r["submitted_at"],
                        "customer_name": r["customer_name"] or "",
                        "customer_email": r["customer_email"] or "",
                        "customer_phone": r["customer_phone"] or "",
                    }
                )
            conn.close()
            self._json(200, {"ok": True, "feedback": rows})
            return

        if path == "/api/admin/queries.php":
            status = (qs.get("status", ["pending"])[0] or "pending").strip().lower()
            conn = db_conn()
            cur = conn.cursor()
            if status == "all":
                cur.execute(
                    """
                    SELECT query_id, query_code, order_code, issue_type, description, status, submitted_at,
                           full_name, contact_number
                    FROM support_queries
                    ORDER BY submitted_at DESC, query_id DESC
                    """
                )
            else:
                cur.execute(
                    """
                    SELECT query_id, query_code, order_code, issue_type, description, status, submitted_at,
                           full_name, contact_number
                    FROM support_queries
                    WHERE status = ?
                    ORDER BY submitted_at DESC, query_id DESC
                    """,
                    (status,),
                )
            rows = [
                {
                    "query_id": r["query_id"],
                    "query_code": r["query_code"],
                    "order_code": r["order_code"] or "",
                    "issue_type": r["issue_type"],
                    "description": r["description"],
                    "status": r["status"],
                    "date": r["submitted_at"],
                    "full_name": r["full_name"] or "",
                    "contact_number": r["contact_number"] or "",
                }
                for r in cur.fetchall()
            ]
            conn.close()
            self._json(200, {"ok": True, "queries": rows})
            return

        if path == "/api/admin/menu.php":
            conn = db_conn()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT mi.item_id, mi.item_code, mi.item_name, mi.price, mi.is_active,
                       COALESCE(mc.category_name, 'Uncategorized') AS category_name
                FROM menu_items mi
                LEFT JOIN menu_categories mc ON mc.category_id = mi.category_id
                ORDER BY mi.item_id DESC
                """
            )
            rows = [
                {
                    "item_id": r["item_id"],
                    "id": r["item_code"],
                    "name": r["item_name"],
                    "price": float(r["price"] or 0),
                    "category": r["category_name"],
                    "isAvailable": bool(r["is_active"]),
                }
                for r in cur.fetchall()
            ]
            conn.close()
            self._json(200, {"ok": True, "menu": rows})
            return

        target = (BASE_DIR / path.lstrip("/")).resolve()
        if not str(target).startswith(str(BASE_DIR)):
            self.send_error(403, "Forbidden")
            return
        self._serve_file(target)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        body = self._body()

        if path == "/api/signup.php":
            name = (body.get("name") or body.get("full_name") or "").strip()
            email = (body.get("email") or "").strip().lower()
            phone = (body.get("phone") or "").strip()
            password = body.get("password") or ""
            confirm = body.get("confirm-password") or body.get("confirmPassword") or password
            if not (name and email and phone and password):
                self._json(400, {"ok": False, "message": "Missing required fields"})
                return
            if password != confirm:
                self._json(400, {"ok": False, "message": "Passwords do not match"})
                return
            conn = db_conn()
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM users WHERE email = ? LIMIT 1", (email,))
            if cur.fetchone():
                conn.close()
                self._json(409, {"ok": False, "message": "Email already registered"})
                return
            cur.execute("SELECT user_id FROM users WHERE phone = ? LIMIT 1", (phone,))
            if cur.fetchone():
                conn.close()
                self._json(409, {"ok": False, "message": "Phone already registered"})
                return
            cur.execute(
                "INSERT INTO users (full_name, email, phone, password_hash, role, created_at) VALUES (?, ?, ?, ?, 'customer', ?)",
                (name, email, phone, hash_password(password), now_ts()),
            )
            uid = cur.lastrowid
            conn.commit()
            cur.execute("SELECT user_id, full_name, email, phone, role, created_at FROM users WHERE user_id = ?", (uid,))
            user = dict(cur.fetchone())
            conn.close()
            self._json(201, {"ok": True, "message": "Signup successful", "user": user})
            return

        if path == "/api/login.php":
            email = (body.get("email") or "").strip().lower()
            password = body.get("password") or ""
            if not (email and password):
                self._json(400, {"ok": False, "message": "Email and password are required"})
                return
            conn = db_conn()
            cur = conn.cursor()
            cur.execute("SELECT user_id, full_name, email, phone, password_hash, role FROM users WHERE email = ? LIMIT 1", (email,))
            row = cur.fetchone()
            conn.close()
            if not row or row["password_hash"] != hash_password(password):
                self._json(401, {"ok": False, "message": "Invalid credentials"})
                return
            self._json(
                200,
                {
                    "ok": True,
                    "message": "Login successful",
                    "user": {
                        "user_id": row["user_id"],
                        "full_name": row["full_name"],
                        "email": row["email"],
                        "phone": row["phone"],
                        "role": row["role"],
                    },
                },
            )
            return

        if path == "/api/orders.php":
            action = (qs.get("action", [""])[0]).strip()
            conn = db_conn()
            cur = conn.cursor()

            if action == "create":
                try:
                    items = body.get("items") or []
                    if not items:
                        self._json(400, {"ok": False, "message": "Order items are required"})
                        return
                    user_id = body.get("user_id")
                    table_code = (body.get("table_code") or "").strip()
                    order_notes = body.get("order_notes")

                    table_id = None
                    if table_code:
                        cur.execute("SELECT table_id FROM dining_tables WHERE table_code = ? LIMIT 1", (table_code,))
                        row = cur.fetchone()
                        if row:
                            table_id = row["table_id"]
                        else:
                            cur.execute(
                                "INSERT INTO dining_tables (table_code, capacity, area, status) VALUES (?, 4, 'indoor', 'occupied')",
                                (table_code,),
                            )
                            table_id = cur.lastrowid

                    order_code = code("ORD")
                    cur.execute(
                        "INSERT INTO orders (order_code, user_id, table_id, order_notes, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
                        (order_code, user_id, table_id, order_notes, now_ts()),
                    )
                    order_id = cur.lastrowid

                    cur.execute("SELECT category_id FROM menu_categories WHERE category_name = 'Uncategorized' LIMIT 1")
                    row = cur.fetchone()
                    category_id = row["category_id"] if row else 1

                    for item in items:
                        item_id = item.get("item_id")
                        item_code = (item.get("item_code") or item.get("id") or "").strip()
                        item_name = (item.get("item_name") or item.get("name") or item_code or "Menu Item").strip()
                        qty = int(item.get("quantity") or 1)
                        unit = float(item.get("unit_price") or item.get("price") or 0)
                        if qty <= 0:
                            qty = 1

                        if not item_id:
                            cur.execute("SELECT item_id FROM menu_items WHERE item_code = ? LIMIT 1", (item_code,))
                            r = cur.fetchone()
                            if r:
                                item_id = r["item_id"]
                            else:
                                if not item_code:
                                    item_code = f"item_{int(time.time())}_{qty}"
                                cur.execute(
                                    "INSERT INTO menu_items (category_id, item_code, item_name, price, is_veg, is_active) VALUES (?, ?, ?, ?, 1, 1)",
                                    (category_id, item_code, item_name, unit),
                                )
                                item_id = cur.lastrowid

                        cur.execute(
                            "INSERT INTO order_items (order_id, item_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                            (order_id, item_id, qty, unit),
                        )

                    conn.commit()
                    self._json(201, {"ok": True, "order_id": order_id, "order_code": order_code})
                except Exception as exc:
                    conn.rollback()
                    self._json(500, {"ok": False, "message": "Order creation failed", "error": str(exc)})
                finally:
                    conn.close()
                return

            if action == "pay":
                try:
                    order_code = (body.get("order_code") or "").strip()
                    method = (body.get("payment_method") or "").strip()
                    coupon = (body.get("coupon_code") or "").strip()
                    if not order_code or method not in ["upi", "card", "cash"]:
                        self._json(400, {"ok": False, "message": "Invalid payment payload"})
                        return

                    cur.execute("SELECT order_id FROM orders WHERE order_code = ? LIMIT 1", (order_code,))
                    row = cur.fetchone()
                    if not row:
                        self._json(404, {"ok": False, "message": "Order not found"})
                        return
                    order_id = row["order_id"]

                    cur.execute("SELECT COALESCE(SUM(quantity * unit_price), 0) AS subtotal FROM order_items WHERE order_id = ?", (order_id,))
                    subtotal = float(cur.fetchone()["subtotal"])

                    discount_percent = 0.0
                    if coupon:
                        cur.execute("SELECT discount_percent FROM coupons WHERE coupon_code = ? AND is_active = 1 LIMIT 1", (coupon,))
                        c = cur.fetchone()
                        if c:
                            discount_percent = float(c["discount_percent"]) / 100.0

                    discount = round(subtotal * discount_percent, 2)
                    net = subtotal - discount
                    cgst = round(net * 0.025, 2)
                    sgst = round(net * 0.025, 2)
                    total = round(net + cgst + sgst, 2)

                    cur.execute("SELECT payment_id FROM payments WHERE order_id = ? LIMIT 1", (order_id,))
                    pay = cur.fetchone()
                    if pay:
                        cur.execute(
                            """
                            UPDATE payments
                            SET subtotal=?, discount_amount=?, cgst_amount=?, sgst_amount=?, grand_total=?,
                                payment_method=?, payment_status='paid', paid_at=?
                            WHERE order_id=?
                            """,
                            (subtotal, discount, cgst, sgst, total, method, now_ts(), order_id),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO payments (order_id, subtotal, discount_amount, cgst_amount, sgst_amount, grand_total, payment_method, payment_status, paid_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 'paid', ?)
                            """,
                            (order_id, subtotal, discount, cgst, sgst, total, method, now_ts()),
                        )
                    cur.execute("UPDATE orders SET status='completed', completed_at=? WHERE order_id=?", (now_ts(), order_id))
                    conn.commit()
                    self._json(
                        200,
                        {
                            "ok": True,
                            "message": "Payment successful",
                            "summary": {
                                "subtotal": subtotal,
                                "discountAmount": discount,
                                "cgstAmount": cgst,
                                "sgstAmount": sgst,
                                "grandTotal": total,
                                "paymentMethod": method,
                            },
                        },
                    )
                except Exception as exc:
                    conn.rollback()
                    self._json(500, {"ok": False, "message": "Payment failed", "error": str(exc)})
                finally:
                    conn.close()
                return

            conn.close()
            self._json(404, {"ok": False, "message": "Unknown action"})
            return

        if path == "/api/feedback.php":
            food = int(body.get("food_rating") or body.get("foodRate") or 0)
            service = int(body.get("service_rating") or body.get("servRate") or 0)
            if food < 1 or service < 1:
                self._json(400, {"ok": False, "message": "Ratings are required"})
                return
            order_code = (body.get("order_code") or "").strip()
            user_id = body.get("user_id")
            comments = body.get("comments")

            conn = db_conn()
            cur = conn.cursor()
            order_id = None
            if order_code:
                cur.execute("SELECT order_id FROM orders WHERE order_code = ? LIMIT 1", (order_code,))
                row = cur.fetchone()
                order_id = row["order_id"] if row else None
            cur.execute(
                "INSERT INTO feedback (order_id, user_id, food_rating, service_rating, comments, submitted_at) VALUES (?, ?, ?, ?, ?, ?)",
                (order_id, user_id, food, service, comments, now_ts()),
            )
            fid = cur.lastrowid
            conn.commit()
            conn.close()
            self._json(201, {"ok": True, "feedback_id": fid})
            return

        if path == "/api/contact.php":
            name = (body.get("name") or "").strip()
            email = (body.get("email") or "").strip()
            phone = (body.get("phone") or "").strip()
            category = (body.get("category") or "").strip()
            message = (body.get("message") or "").strip()
            if not (name and email and category and message):
                self._json(400, {"ok": False, "message": "Missing required fields"})
                return
            conn = db_conn()
            cur = conn.cursor()
            mid = code("MSG")
            cur.execute(
                "INSERT INTO contact_messages (message_code, full_name, email, phone, category, message_text, status, submitted_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
                (mid, name, email, phone, category, message, now_ts()),
            )
            dbid = cur.lastrowid
            conn.commit()
            conn.close()
            self._json(201, {"ok": True, "message_id": dbid, "message_code": mid})
            return

        if path == "/api/query.php":
            full_name = (body.get("fullName") or body.get("full_name") or "").strip()
            contact_number = (body.get("contactNumber") or body.get("contact_number") or "").strip()
            order_code = (body.get("orderId") or body.get("order_code") or "").strip()
            issue = (body.get("issueType") or body.get("issue_type") or "").strip()
            description = (body.get("description") or "").strip()
            photo = (body.get("photo_filename") or "").strip()
            if not (full_name and contact_number and issue and description):
                self._json(400, {"ok": False, "message": "Missing required fields"})
                return
            conn = db_conn()
            cur = conn.cursor()
            qid = code("QRY")
            cur.execute(
                "INSERT INTO support_queries (query_code, full_name, contact_number, order_code, issue_type, description, photo_filename, status, submitted_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
                (qid, full_name, contact_number, order_code, issue, description, photo, now_ts()),
            )
            rowid = cur.lastrowid
            conn.commit()
            conn.close()
            self._json(201, {"ok": True, "query_id": rowid, "query_code": qid})
            return

        if path == "/api/admin/query_resolve.php":
            query_id = body.get("query_id")
            query_code = (body.get("query_code") or "").strip()
            if not query_id and not query_code:
                self._json(400, {"ok": False, "message": "query_id or query_code is required"})
                return
            conn = db_conn()
            cur = conn.cursor()
            if query_id:
                cur.execute("UPDATE support_queries SET status='resolved' WHERE query_id = ?", (query_id,))
            else:
                cur.execute("UPDATE support_queries SET status='resolved' WHERE query_code = ?", (query_code,))
            affected = cur.rowcount
            conn.commit()
            conn.close()
            if affected == 0:
                self._json(404, {"ok": False, "message": "Ticket not found"})
            else:
                self._json(200, {"ok": True, "message": "Ticket marked as resolved"})
            return

        if path == "/api/admin/menu_item.php":
            action = (body.get("action") or "").strip().lower()
            conn = db_conn()
            cur = conn.cursor()
            try:
                if action == "add":
                    name = (body.get("name") or "").strip()
                    category = (body.get("category") or "").strip() or "Uncategorized"
                    price = float(body.get("price") or 0)
                    if not name:
                        self._json(400, {"ok": False, "message": "name is required"})
                        return

                    cur.execute("INSERT OR IGNORE INTO menu_categories (category_name) VALUES (?)", (category,))
                    cur.execute("SELECT category_id FROM menu_categories WHERE category_name = ? LIMIT 1", (category,))
                    cat = cur.fetchone()
                    category_id = cat["category_id"] if cat else 1
                    item_code = (name.lower().replace(" ", "_"))[:32] + f"_{int(time.time())}"

                    cur.execute(
                        "INSERT INTO menu_items (category_id, item_code, item_name, price, is_veg, is_active) VALUES (?, ?, ?, ?, 1, 1)",
                        (category_id, item_code, name, price),
                    )
                    conn.commit()
                    self._json(201, {"ok": True, "item_id": cur.lastrowid})
                    return

                if action == "update_price":
                    item_id = body.get("item_id")
                    price = float(body.get("price") or 0)
                    if not item_id:
                        self._json(400, {"ok": False, "message": "item_id is required"})
                        return
                    cur.execute("UPDATE menu_items SET price = ? WHERE item_id = ?", (price, item_id))
                    conn.commit()
                    self._json(200, {"ok": True})
                    return

                if action == "toggle":
                    item_id = body.get("item_id")
                    is_active = 1 if body.get("is_active") else 0
                    if not item_id:
                        self._json(400, {"ok": False, "message": "item_id is required"})
                        return
                    cur.execute("UPDATE menu_items SET is_active = ? WHERE item_id = ?", (is_active, item_id))
                    conn.commit()
                    self._json(200, {"ok": True})
                    return

                if action == "delete":
                    item_id = body.get("item_id")
                    if not item_id:
                        self._json(400, {"ok": False, "message": "item_id is required"})
                        return
                    cur.execute("DELETE FROM menu_items WHERE item_id = ?", (item_id,))
                    conn.commit()
                    self._json(200, {"ok": True})
                    return

                if action == "reset_defaults":
                    items = body.get("items") or []
                    if not isinstance(items, list) or not items:
                        self._json(400, {"ok": False, "message": "items array is required"})
                        return

                    cur.execute("DELETE FROM menu_items")
                    cur.execute("DELETE FROM menu_categories")
                    cur.execute("INSERT OR IGNORE INTO menu_categories (category_name) VALUES ('Uncategorized')")

                    for i, item in enumerate(items):
                        name = (item.get("name") or "").strip()
                        category = (item.get("category") or "").strip() or "Uncategorized"
                        price = float(item.get("price") or 0)
                        is_active = 1 if item.get("isAvailable", True) else 0
                        if not name:
                            continue
                        cur.execute("INSERT OR IGNORE INTO menu_categories (category_name) VALUES (?)", (category,))
                        cur.execute("SELECT category_id FROM menu_categories WHERE category_name = ? LIMIT 1", (category,))
                        cat = cur.fetchone()
                        category_id = cat["category_id"] if cat else 1
                        item_code = (name.lower().replace(" ", "_"))[:32] + f"_{int(time.time())}_{i}"
                        cur.execute(
                            "INSERT INTO menu_items (category_id, item_code, item_name, price, is_veg, is_active) VALUES (?, ?, ?, ?, 1, ?)",
                            (category_id, item_code, name, price, is_active),
                        )

                    conn.commit()
                    self._json(200, {"ok": True})
                    return

                self._json(400, {"ok": False, "message": "Unknown action"})
            finally:
                conn.close()
            return

        self._json(404, {"ok": False, "message": "Route not found"})


if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"RestroFlow Python server running at http://{host}:{port}")
    server.serve_forever()
