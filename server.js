const express = require("express");
const cors = require("cors");
const dotenv = require("dotenv");
const bcrypt = require("bcryptjs");
const mysql = require("mysql2/promise");
const path = require("path");

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname)));

const pool = mysql.createPool({
  host: process.env.DB_HOST || "localhost",
  port: Number(process.env.DB_PORT || 3306),
  user: process.env.DB_USER || "root",
  password: process.env.DB_PASSWORD || "",
  database: process.env.DB_NAME || "restroflow_db",
  waitForConnections: true,
  connectionLimit: 10
});

function makeCode(prefix) {
  return `${prefix}${Date.now()}`;
}

async function getOrderSubtotal(orderId) {
  const [rows] = await pool.query(
    "SELECT COALESCE(SUM(line_total), 0) AS subtotal FROM order_items WHERE order_id = ?",
    [orderId]
  );
  return Number(rows[0].subtotal || 0);
}

app.get("/api/health", async (_req, res) => {
  try {
    await pool.query("SELECT 1");
    res.json({ ok: true, message: "Server and DB are connected" });
  } catch (err) {
    res.status(500).json({ ok: false, message: "DB connection failed", error: err.message });
  }
});

app.get("/", (_req, res) => {
  res.sendFile(path.join(__dirname, "home_page.html"));
});

app.post("/api/signup", async (req, res) => {
  try {
    const fullName = (req.body.name || req.body.full_name || "").trim();
    const email = (req.body.email || "").trim().toLowerCase();
    const phone = (req.body.phone || "").trim();
    const password = req.body.password || "";
    const confirmPassword = req.body["confirm-password"] || req.body.confirmPassword || password;

    if (!fullName || !email || !phone || !password) {
      return res.status(400).json({ ok: false, message: "Missing required fields" });
    }
    if (password !== confirmPassword) {
      return res.status(400).json({ ok: false, message: "Passwords do not match" });
    }

    const [emailRows] = await pool.query("SELECT user_id FROM users WHERE email = ?", [email]);
    if (emailRows.length) {
      return res.status(409).json({ ok: false, message: "Email already registered" });
    }

    const [phoneRows] = await pool.query("SELECT user_id FROM users WHERE phone = ?", [phone]);
    if (phoneRows.length) {
      return res.status(409).json({ ok: false, message: "Phone already registered" });
    }

    const passwordHash = await bcrypt.hash(password, 10);
    const [result] = await pool.query(
      "INSERT INTO users (full_name, email, phone, password_hash, role) VALUES (?, ?, ?, ?, 'customer')",
      [fullName, email, phone, passwordHash]
    );

    const [users] = await pool.query(
      "SELECT user_id, full_name, email, phone, role, created_at FROM users WHERE user_id = ?",
      [result.insertId]
    );

    return res.status(201).json({ ok: true, message: "Signup successful", user: users[0] });
  } catch (err) {
    return res.status(500).json({ ok: false, message: "Signup failed", error: err.message });
  }
});

app.post("/api/login", async (req, res) => {
  try {
    const email = (req.body.email || "").trim().toLowerCase();
    const password = req.body.password || "";
    if (!email || !password) {
      return res.status(400).json({ ok: false, message: "Email and password are required" });
    }

    const [rows] = await pool.query(
      "SELECT user_id, full_name, email, phone, password_hash, role FROM users WHERE email = ?",
      [email]
    );
    if (!rows.length) {
      return res.status(401).json({ ok: false, message: "Invalid credentials" });
    }

    const user = rows[0];
    const isValid = await bcrypt.compare(password, user.password_hash);
    if (!isValid) {
      return res.status(401).json({ ok: false, message: "Invalid credentials" });
    }

    return res.json({
      ok: true,
      message: "Login successful",
      user: {
        user_id: user.user_id,
        full_name: user.full_name,
        email: user.email,
        phone: user.phone,
        role: user.role
      }
    });
  } catch (err) {
    return res.status(500).json({ ok: false, message: "Login failed", error: err.message });
  }
});

app.post("/api/orders", async (req, res) => {
  const connection = await pool.getConnection();
  try {
    const userId = req.body.user_id || null;
    let tableId = req.body.table_id || null;
    const tableCode = (req.body.table_code || "").trim();
    const orderNotes = req.body.order_notes || req.body.orderNotes || null;
    const items = Array.isArray(req.body.items) ? req.body.items : [];

    if (!items.length) {
      return res.status(400).json({ ok: false, message: "Order items are required" });
    }

    await connection.beginTransaction();

    if (!tableId && tableCode) {
      const [tableRows] = await connection.query(
        "SELECT table_id FROM dining_tables WHERE table_code = ? LIMIT 1",
        [tableCode]
      );
      if (tableRows.length) {
        tableId = tableRows[0].table_id;
      } else {
        const [newTable] = await connection.query(
          "INSERT INTO dining_tables (table_code, capacity, area, status) VALUES (?, 4, 'indoor', 'occupied')",
          [tableCode]
        );
        tableId = newTable.insertId;
      }
    }

    const orderCode = makeCode("ORD");
    const [orderResult] = await connection.query(
      "INSERT INTO orders (order_code, user_id, table_id, order_notes, status) VALUES (?, ?, ?, ?, 'pending')",
      [orderCode, userId, tableId, orderNotes]
    );
    const orderId = orderResult.insertId;

    for (const item of items) {
      let itemId = item.item_id ? Number(item.item_id) : null;
      const quantity = Number(item.quantity || 1);
      const unitPrice = Number(item.unit_price ?? item.price);
      const itemCode = String(item.item_code || item.id || "").trim();
      const itemName = String(item.item_name || item.name || itemCode || "Menu Item").trim();

      if (quantity <= 0 || Number.isNaN(unitPrice)) {
        throw new Error("Invalid item payload");
      }

      if (!itemId) {
        const [existingItems] = await connection.query(
          "SELECT item_id FROM menu_items WHERE item_code = ? LIMIT 1",
          [itemCode]
        );

        if (existingItems.length) {
          itemId = existingItems[0].item_id;
        } else {
          let uncategorizedId;
          const [categories] = await connection.query(
            "SELECT category_id FROM menu_categories WHERE category_name = 'Uncategorized' LIMIT 1"
          );

          if (categories.length) {
            uncategorizedId = categories[0].category_id;
          } else {
            const [newCategory] = await connection.query(
              "INSERT INTO menu_categories (category_name) VALUES ('Uncategorized')"
            );
            uncategorizedId = newCategory.insertId;
          }

          const safeCode = itemCode || `item_${Date.now()}`;
          const [newItem] = await connection.query(
            `INSERT INTO menu_items (category_id, item_code, item_name, price, is_veg, is_active)
             VALUES (?, ?, ?, ?, TRUE, TRUE)`,
            [uncategorizedId, safeCode, itemName, unitPrice]
          );
          itemId = newItem.insertId;
        }
      }

      await connection.query(
        "INSERT INTO order_items (order_id, item_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
        [orderId, itemId, quantity, unitPrice]
      );
    }

    await connection.commit();
    return res.status(201).json({ ok: true, order_id: orderId, order_code: orderCode });
  } catch (err) {
    await connection.rollback();
    return res.status(500).json({ ok: false, message: "Order creation failed", error: err.message });
  } finally {
    connection.release();
  }
});

app.get("/api/orders/:orderCode/bill", async (req, res) => {
  try {
    const { orderCode } = req.params;
    const [rows] = await pool.query(
      `SELECT o.order_id, o.order_code, o.created_at, o.status,
              COALESCE(t.table_code, 'Takeaway') AS table_name,
              mi.item_name, oi.quantity, oi.unit_price, oi.line_total
       FROM orders o
       LEFT JOIN dining_tables t ON t.table_id = o.table_id
       JOIN order_items oi ON oi.order_id = o.order_id
       JOIN menu_items mi ON mi.item_id = oi.item_id
       WHERE o.order_code = ?`,
      [orderCode]
    );
    if (!rows.length) {
      return res.status(404).json({ ok: false, message: "Order not found" });
    }
    return res.json({ ok: true, bill: rows });
  } catch (err) {
    return res.status(500).json({ ok: false, message: "Failed to fetch bill", error: err.message });
  }
});

app.post("/api/orders/:orderCode/pay", async (req, res) => {
  const connection = await pool.getConnection();
  try {
    const { orderCode } = req.params;
    const paymentMethod = req.body.payment_method;
    const couponCode = req.body.coupon_code || null;
    if (!["upi", "card", "cash"].includes(paymentMethod)) {
      return res.status(400).json({ ok: false, message: "Invalid payment method" });
    }

    const [orderRows] = await connection.query("SELECT order_id FROM orders WHERE order_code = ?", [orderCode]);
    if (!orderRows.length) {
      return res.status(404).json({ ok: false, message: "Order not found" });
    }
    const orderId = orderRows[0].order_id;

    let discountPercent = 0;
    if (couponCode) {
      const [couponRows] = await connection.query(
        "SELECT discount_percent FROM coupons WHERE coupon_code = ? AND is_active = TRUE AND CURDATE() BETWEEN valid_from AND valid_to",
        [couponCode]
      );
      if (couponRows.length) {
        discountPercent = Number(couponRows[0].discount_percent) / 100;
      }
    }

    const subtotal = await getOrderSubtotal(orderId);
    const discountAmount = Number((subtotal * discountPercent).toFixed(2));
    const netSubtotal = subtotal - discountAmount;
    const cgstAmount = Number((netSubtotal * 0.025).toFixed(2));
    const sgstAmount = Number((netSubtotal * 0.025).toFixed(2));
    const grandTotal = Number((netSubtotal + cgstAmount + sgstAmount).toFixed(2));

    await connection.beginTransaction();
    await connection.query(
      `INSERT INTO payments
       (order_id, subtotal, discount_amount, cgst_amount, sgst_amount, grand_total, payment_method, payment_status, paid_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, 'paid', NOW())
       ON DUPLICATE KEY UPDATE
       subtotal = VALUES(subtotal),
       discount_amount = VALUES(discount_amount),
       cgst_amount = VALUES(cgst_amount),
       sgst_amount = VALUES(sgst_amount),
       grand_total = VALUES(grand_total),
       payment_method = VALUES(payment_method),
       payment_status = 'paid',
       paid_at = NOW()`,
      [orderId, subtotal, discountAmount, cgstAmount, sgstAmount, grandTotal, paymentMethod]
    );
    await connection.query(
      "UPDATE orders SET status = 'completed', completed_at = NOW() WHERE order_id = ?",
      [orderId]
    );
    await connection.commit();

    return res.json({
      ok: true,
      message: "Payment successful",
      summary: { subtotal, discountAmount, cgstAmount, sgstAmount, grandTotal, paymentMethod }
    });
  } catch (err) {
    await connection.rollback();
    return res.status(500).json({ ok: false, message: "Payment failed", error: err.message });
  } finally {
    connection.release();
  }
});

app.post("/api/feedback", async (req, res) => {
  try {
    const orderCode = req.body.order_code || null;
    const userId = req.body.user_id || null;
    const foodRating = Number(req.body.food_rating || req.body.foodRate);
    const serviceRating = Number(req.body.service_rating || req.body.servRate);
    const comments = req.body.comments || null;

    if (!foodRating || !serviceRating) {
      return res.status(400).json({ ok: false, message: "Ratings are required" });
    }

    const [result] = await pool.query(
      `INSERT INTO feedback (order_id, user_id, food_rating, service_rating, comments)
       VALUES ((SELECT order_id FROM orders WHERE order_code = ? LIMIT 1), ?, ?, ?, ?)`,
      [orderCode, userId, foodRating, serviceRating, comments]
    );

    return res.status(201).json({ ok: true, feedback_id: result.insertId });
  } catch (err) {
    return res.status(500).json({ ok: false, message: "Feedback submission failed", error: err.message });
  }
});

app.post("/api/query", async (req, res) => {
  try {
    const queryCode = makeCode("QRY");
    const fullName = req.body.fullName || req.body.full_name;
    const contactNumber = req.body.contactNumber || req.body.contact_number;
    const orderCode = req.body.orderId || req.body.order_code || null;
    const issueType = req.body.issueType || req.body.issue_type;
    const description = req.body.description;
    const photoFilename = req.body.photo_filename || null;

    if (!fullName || !contactNumber || !issueType || !description) {
      return res.status(400).json({ ok: false, message: "Missing required fields" });
    }

    const [result] = await pool.query(
      `INSERT INTO support_queries
       (query_code, full_name, contact_number, order_code, issue_type, description, photo_filename, status)
       VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')`,
      [queryCode, fullName, contactNumber, orderCode, issueType, description, photoFilename]
    );

    return res.status(201).json({ ok: true, query_id: result.insertId, query_code: queryCode });
  } catch (err) {
    return res.status(500).json({ ok: false, message: "Query submission failed", error: err.message });
  }
});

app.post("/api/contact", async (req, res) => {
  try {
    const messageCode = makeCode("MSG");
    const fullName = req.body.name || req.body.full_name;
    const email = req.body.email;
    const phone = req.body.phone || null;
    const category = req.body.category;
    const messageText = req.body.message || req.body.message_text;

    if (!fullName || !email || !category || !messageText) {
      return res.status(400).json({ ok: false, message: "Missing required fields" });
    }

    const [result] = await pool.query(
      `INSERT INTO contact_messages
       (message_code, full_name, email, phone, category, message_text, status)
       VALUES (?, ?, ?, ?, ?, ?, 'pending')`,
      [messageCode, fullName, email, phone, category, messageText]
    );

    return res.status(201).json({ ok: true, message_id: result.insertId, message_code: messageCode });
  } catch (err) {
    return res.status(500).json({ ok: false, message: "Contact submission failed", error: err.message });
  }
});

const port = Number(process.env.PORT || 5000);
app.listen(port, () => {
  console.log(`RestroFlow API running on http://localhost:${port}`);
});
