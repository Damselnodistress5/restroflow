
USE restroflow_db;


-- 1) Check if email already exists
SELECT user_id
FROM users
WHERE email = ?;

-- 2) Check if phone already exists
SELECT user_id
FROM users
WHERE phone = ?;

-- 3) Create new user
INSERT INTO users (full_name, email, phone, password_hash, role)
VALUES (?, ?, ?, ?, 'customer');

-- 4) Return created user (without password)
SELECT user_id, full_name, email, phone, role, created_at
FROM users
WHERE user_id = LAST_INSERT_ID();


-- =========================================
-- AUTH: /api/login
-- Input: email, password
-- =========================================

-- 1) Fetch user with password_hash (compare hash in backend)
SELECT user_id, full_name, email, phone, password_hash, role
FROM users
WHERE email = ?;

-- 2) Optional: update last login time (add column first if needed)
-- ALTER TABLE users ADD COLUMN last_login_at DATETIME NULL;
-- UPDATE users SET last_login_at = NOW() WHERE user_id = ?;


-- =========================================
-- ORDER: /api/orders (create order + items)
-- Input:
--   order_code, user_id (nullable), table_id (nullable), order_notes
--   items[]: [{item_id, quantity, unit_price}]
-- =========================================

-- Step A: Create order header
INSERT INTO orders (order_code, user_id, table_id, order_notes, status)
VALUES (?, ?, ?, ?, 'pending');

-- Step B: Get created order id
SELECT LAST_INSERT_ID() AS order_id;

-- Step C: Insert each item (run once per item from backend loop)
INSERT INTO order_items (order_id, item_id, quantity, unit_price)
VALUES (?, ?, ?, ?);


-- =========================================
-- BILLING: /api/orders/:orderCode/bill
-- =========================================

SELECT
  o.order_id,
  o.order_code,
  o.created_at,
  o.status,
  COALESCE(t.table_code, 'Takeaway') AS table_name,
  mi.item_name,
  oi.quantity,
  oi.unit_price,
  oi.line_total
FROM orders o
LEFT JOIN dining_tables t ON t.table_id = o.table_id
JOIN order_items oi ON oi.order_id = o.order_id
JOIN menu_items mi ON mi.item_id = oi.item_id
WHERE o.order_code = ?;


-- =========================================
-- PAYMENT: /api/orders/:orderCode/pay
-- Input: payment_method, coupon_code(optional)
-- Tax: CGST 2.5%, SGST 2.5%
-- =========================================

-- 1) Subtotal
SELECT
  o.order_id,
  o.order_code,
  SUM(oi.line_total) AS subtotal
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_code = ?
GROUP BY o.order_id, o.order_code;

-- 2) Coupon percent (if coupon provided and active)
SELECT discount_percent
FROM coupons
WHERE coupon_code = ?
  AND is_active = TRUE
  AND CURDATE() BETWEEN valid_from AND valid_to;

-- 3) Save payment row (final values calculated in backend)
INSERT INTO payments (
  order_id, subtotal, discount_amount, cgst_amount, sgst_amount, grand_total, payment_method, payment_status, paid_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, 'paid', NOW());

-- 4) Mark order complete
UPDATE orders
SET status = 'completed', completed_at = NOW()
WHERE order_id = ?;


-- =========================================
-- FEEDBACK: /api/feedback
-- Input: order_code(optional), user_id(optional), food_rating, service_rating, comments
-- =========================================

INSERT INTO feedback (order_id, user_id, food_rating, service_rating, comments)
VALUES (
  (SELECT order_id FROM orders WHERE order_code = ? LIMIT 1),
  ?,
  ?,
  ?,
  ?
);


-- =========================================
-- SUPPORT QUERY: /api/query
-- =========================================

INSERT INTO support_queries (
  query_code, full_name, contact_number, order_code, issue_type, description, photo_filename, status
)
VALUES (?, ?, ?, ?, ?, ?, ?, 'pending');


-- =========================================
-- CONTACT MESSAGE: /api/contact
-- =========================================

INSERT INTO contact_messages (
  message_code, full_name, email, phone, category, message_text, status
)
VALUES (?, ?, ?, ?, ?, ?, 'pending');


-- =========================================
-- Admin useful queries
-- =========================================

-- Pending orders
SELECT order_code, created_at, status
FROM orders
WHERE status = 'pending'
ORDER BY created_at ASC;

-- Daily sales summary
SELECT DATE(paid_at) AS sale_date, COUNT(*) AS total_bills, SUM(grand_total) AS total_revenue
FROM payments
WHERE payment_status = 'paid'
GROUP BY DATE(paid_at)
ORDER BY sale_date DESC;

