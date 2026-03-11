

DROP DATABASE IF EXISTS restroflow_db;
CREATE DATABASE restroflow_db;
USE restroflow_db;

-- 1) Users (signup/login)
CREATE TABLE users (
  user_id INT AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(100) NOT NULL,
  email VARCHAR(120) NOT NULL UNIQUE,
  phone VARCHAR(20) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('customer', 'admin', 'staff') DEFAULT 'customer',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2) Dining tables (table plan)
CREATE TABLE dining_tables (
  table_id INT AUTO_INCREMENT PRIMARY KEY,
  table_code VARCHAR(20) NOT NULL UNIQUE,
  capacity TINYINT UNSIGNED NOT NULL DEFAULT 4,
  area ENUM('indoor', 'patio') DEFAULT 'indoor',
  status ENUM('available', 'occupied', 'reserved', 'cleaning') DEFAULT 'available'
);

-- 3) Menu categories
CREATE TABLE menu_categories (
  category_id INT AUTO_INCREMENT PRIMARY KEY,
  category_name VARCHAR(60) NOT NULL UNIQUE
);

-- 4) Menu items
CREATE TABLE menu_items (
  item_id INT AUTO_INCREMENT PRIMARY KEY,
  category_id INT NOT NULL,
  item_code VARCHAR(50) NOT NULL UNIQUE,
  item_name VARCHAR(120) NOT NULL,
  price DECIMAL(10,2) NOT NULL CHECK (price >= 0),
  is_veg BOOLEAN DEFAULT TRUE,
  is_active BOOLEAN DEFAULT TRUE,
  FOREIGN KEY (category_id) REFERENCES menu_categories(category_id)
);

-- 5) Coupons / promo codes
CREATE TABLE coupons (
  coupon_id INT AUTO_INCREMENT PRIMARY KEY,
  coupon_code VARCHAR(30) NOT NULL UNIQUE,
  discount_percent DECIMAL(5,2) NOT NULL CHECK (discount_percent >= 0 AND discount_percent <= 100),
  valid_from DATE NOT NULL,
  valid_to DATE NOT NULL,
  is_active BOOLEAN DEFAULT TRUE
);

-- 6) Orders (header)
CREATE TABLE orders (
  order_id INT AUTO_INCREMENT PRIMARY KEY,
  order_code VARCHAR(30) NOT NULL UNIQUE,
  user_id INT NULL,
  table_id INT NULL,
  order_notes TEXT NULL,
  status ENUM('pending', 'completed', 'cancelled') DEFAULT 'pending',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  FOREIGN KEY (user_id) REFERENCES users(user_id),
  FOREIGN KEY (table_id) REFERENCES dining_tables(table_id)
);

-- 7) Order items (line items)
CREATE TABLE order_items (
  order_item_id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  item_id INT NOT NULL,
  quantity INT NOT NULL CHECK (quantity > 0),
  unit_price DECIMAL(10,2) NOT NULL CHECK (unit_price >= 0),
  line_total DECIMAL(10,2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
  FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
  FOREIGN KEY (item_id) REFERENCES menu_items(item_id)
);

-- 8) Billing + payment details
CREATE TABLE payments (
  payment_id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL UNIQUE,
  subtotal DECIMAL(10,2) NOT NULL CHECK (subtotal >= 0),
  discount_amount DECIMAL(10,2) DEFAULT 0 CHECK (discount_amount >= 0),
  cgst_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
  sgst_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
  grand_total DECIMAL(10,2) NOT NULL CHECK (grand_total >= 0),
  payment_method ENUM('upi', 'card', 'cash') NOT NULL,
  payment_status ENUM('pending', 'paid', 'failed') DEFAULT 'paid',
  paid_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
);

-- 9) Feedback
CREATE TABLE feedback (
  feedback_id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NULL,
  user_id INT NULL,
  food_rating TINYINT NOT NULL CHECK (food_rating BETWEEN 1 AND 5),
  service_rating TINYINT NOT NULL CHECK (service_rating BETWEEN 1 AND 5),
  comments TEXT NULL,
  submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE SET NULL,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

-- 10) Support queries
CREATE TABLE support_queries (
  query_id INT AUTO_INCREMENT PRIMARY KEY,
  query_code VARCHAR(30) NOT NULL UNIQUE,
  full_name VARCHAR(100) NOT NULL,
  contact_number VARCHAR(20) NOT NULL,
  order_code VARCHAR(30) NULL,
  issue_type ENUM('payment', 'missing-item', 'food-quality', 'staff-service', 'other') NOT NULL,
  description TEXT NOT NULL,
  photo_filename VARCHAR(255) NULL,
  status ENUM('pending', 'in-progress', 'resolved') DEFAULT 'pending',
  submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 11) Contact form messages
CREATE TABLE contact_messages (
  message_id INT AUTO_INCREMENT PRIMARY KEY,
  message_code VARCHAR(30) NOT NULL UNIQUE,
  full_name VARCHAR(100) NOT NULL,
  email VARCHAR(120) NOT NULL,
  phone VARCHAR(20) NULL,
  category ENUM('general', 'order-issue', 'reservation', 'feedback') NOT NULL,
  message_text TEXT NOT NULL,
  status ENUM('pending', 'responded', 'closed') DEFAULT 'pending',
  submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP
);


-- Useful report query: bill summary for all completed orders
CREATE OR REPLACE VIEW v_order_bill_summary AS
SELECT
  o.order_code,
  o.created_at,
  o.status,
  COALESCE(u.full_name, 'Guest') AS customer_name,
  COALESCE(t.table_code, 'Takeaway') AS table_name,
  p.subtotal,
  p.discount_amount,
  p.cgst_amount,
  p.sgst_amount,
  p.grand_total,
  p.payment_method
FROM orders o
LEFT JOIN users u ON o.user_id = u.user_id
LEFT JOIN dining_tables t ON o.table_id = t.table_id
LEFT JOIN payments p ON o.order_id = p.order_id;
