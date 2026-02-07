-- Museum Management System Database Schema
-- Created: 2026-01-25

-- Create database if it doesn't exist
-- CREATE DATABASE IF NOT EXISTS museum_db;
-- USE museum_db;

-- ===== USERS TABLE =====
CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    phone VARCHAR(15),
    role ENUM('user', 'admin') DEFAULT 'user',
    status ENUM('active', 'inactive') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email (email)
);

-- ===== INSERT DEFAULT ADMIN USER =====
INSERT IGNORE INTO users (name, email, password, phone, role, status) 
VALUES ('Administrator', 'admin@gmail.com', 'Admin@123', '9999999999', 'admin', 'active');

-- ===== INSERT SAMPLE USERS =====
INSERT IGNORE INTO users (name, email, password, phone, role, status) 
VALUES 
('Arun Kumar', 'arun@gmail.com', 'User@123', '9876543210', 'user', 'active'),
('Priya Singh', 'priya@gmail.com', 'User@123', '9123456780', 'user', 'active'),
('Karthik Raj', 'karthik@gmail.com', 'User@123', '9001122334', 'user', 'inactive');

-- ===== TICKETS TABLE =====
CREATE TABLE IF NOT EXISTS tickets (
    id INT PRIMARY KEY AUTO_INCREMENT,
    ticket_code VARCHAR(50),
    museum_name VARCHAR(255) NOT NULL,
    user_name VARCHAR(100) NOT NULL,
    user_email VARCHAR(100) NOT NULL,
    phone VARCHAR(15),
    visit_date DATE NOT NULL,
    visit_time TIME,
    ticket_qty INT DEFAULT 1,
    total_price DECIMAL(10, 2),
    booking_status ENUM('confirmed', 'cancelled', 'pending') DEFAULT 'confirmed',
    payment_method ENUM('manual_upi', 'razorpay', 'card') DEFAULT 'manual_upi',
    payment_status ENUM('completed', 'pending', 'failed') DEFAULT 'pending',
    payment_date DATETIME,
    used INT DEFAULT 0,
    booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_museum (museum_name),
    INDEX idx_email (user_email),
    INDEX idx_date (visit_date),
    INDEX idx_code (ticket_code)
);

-- ===== ARTIFACTS TABLE (Optional - for future use) =====
CREATE TABLE IF NOT EXISTS artifacts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    museum_name VARCHAR(255) NOT NULL,
    artifact_name VARCHAR(255) NOT NULL,
    artifact_period VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_museum (museum_name)
);

-- ===== FEEDBACK TABLE (Optional - for future use) =====
CREATE TABLE IF NOT EXISTS feedback (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_email VARCHAR(100),
    museum_name VARCHAR(255),
    rating INT,
    comments TEXT,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_museum (museum_name)
);
