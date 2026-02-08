#!/usr/bin/env python3
"""Quick import + migration script"""
import pymysql
import pymysql.cursors
import os
import sys

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Ishwarya@123")
DB_NAME = os.getenv("DB_NAME", "museum_db")

print(f"🔄 Connecting to MySQL at {DB_HOST}...")

# Connect without database first to create it
conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, charset='utf8mb4')
cur = conn.cursor()

# Create database
print("📦 Creating database...")
cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
conn.commit()

# Switch to database
conn.select_db(DB_NAME)

# Read and execute SQL file
sql_path = os.path.join(os.path.dirname(__file__), '../database/museum.sql')
print(f"📄 Reading SQL from {sql_path}...")
with open(sql_path, 'r', encoding='utf-8') as f:
    sql_content = f.read()

# Split by semicolon and execute statements
sql_statements = sql_content.split(';')
print(f"📊 Executing {len(sql_statements)} SQL statements...")
for i, stmt in enumerate(sql_statements):
    s = stmt.strip()
    if s and not s.startswith('--'):  # Skip comments
        try:
            cur.execute(s)
        except Exception as e:
            print(f"⚠️ Statement {i}: {e}")

conn.commit()
cur.close()
conn.close()

print("✅ Schema imported successfully!")

# Now run migration inline
print("\n🔄 Running payment migration...")
conn = pymysql.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)
cur = conn.cursor()

migrations = [
    {
        'name': 'ticket_code column',
        'sql': "ALTER TABLE tickets ADD COLUMN ticket_code VARCHAR(50) AFTER id;",
        'check': "SHOW COLUMNS FROM tickets WHERE Field='ticket_code'"
    },
    {
        'name': 'phone column',
        'sql': "ALTER TABLE tickets ADD COLUMN phone VARCHAR(15) AFTER user_email;",
        'check': "SHOW COLUMNS FROM tickets WHERE Field='phone'"
    },
    {
        'name': 'visit_time column',
        'sql': "ALTER TABLE tickets ADD COLUMN visit_time TIME AFTER visit_date;",
        'check': "SHOW COLUMNS FROM tickets WHERE Field='visit_time'"
    },
    {
        'name': 'payment_method column',
        'sql': "ALTER TABLE tickets ADD COLUMN payment_method ENUM('manual_upi', 'razorpay', 'card') DEFAULT 'manual_upi' AFTER booking_status;",
        'check': "SHOW COLUMNS FROM tickets WHERE Field='payment_method'"
    },
    {
        'name': 'payment_status column',
        'sql': "ALTER TABLE tickets ADD COLUMN payment_status ENUM('completed', 'pending', 'failed') DEFAULT 'pending' AFTER payment_method;",
        'check': "SHOW COLUMNS FROM tickets WHERE Field='payment_status'"
    },
    {
        'name': 'payment_date column',
        'sql': "ALTER TABLE tickets ADD COLUMN payment_date DATETIME AFTER payment_status;",
        'check': "SHOW COLUMNS FROM tickets WHERE Field='payment_date'"
    },
    {
        'name': 'used column',
        'sql': "ALTER TABLE tickets ADD COLUMN used INT DEFAULT 0 AFTER payment_date;",
        'check': "SHOW COLUMNS FROM tickets WHERE Field='used'"
    }
]

for migration in migrations:
    try:
        cur.execute(migration['check'])
        if cur.fetchone():
            print(f"✅ {migration['name']} already exists - skipping")
        else:
            cur.execute(migration['sql'])
            conn.commit()
            print(f"✅ Added {migration['name']}")
    except Exception as e:
        if "already exists" in str(e) or "Duplicate" in str(e):
            print(f"✅ {migration['name']} already exists - skipping")
        else:
            print(f"⚠️ {migration['name']}: {e}")

cur.close()
conn.close()

print("\n✅ All done! Database ready with all tables and columns.")
