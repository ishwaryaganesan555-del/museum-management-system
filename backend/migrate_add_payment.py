#!/usr/bin/env python3
"""
✅ Database Migration Script
Add payment-related columns to the tickets table

Run this script once to add payment fields to your existing database.
"""

import pymysql
import os
import re

# Prefer environment variables. If not set, try to parse backend/app.py, then prompt.
DB_HOST = os.getenv('DB_HOST', '')
DB_USER = os.getenv('DB_USER', '')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', '')


def try_load_from_app_py():
    """Attempt to parse DB connection values from backend/app.py as a convenience."""
    app_path = os.path.join(os.path.dirname(__file__), 'app.py')
    if not os.path.exists(app_path):
        return None
    try:
        text = open(app_path, 'r', encoding='utf-8').read()
        m = re.search(r"pymysql.connect\(([\s\S]*?)\)", text)
        if not m:
            return None
        inside = m.group(1)
        def find_kw(k):
            mm = re.search(rf"{k}\s*=\s*['\"]([^'\"]+)['\"]", inside)
            return mm.group(1) if mm else None
        host = find_kw('host')
        user = find_kw('user')
        password = find_kw('password')
        database = find_kw('database')
        return {'host': host, 'user': user, 'password': password, 'database': database}
    except Exception:
        return None


def get_db_config_interactive():
    global DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
    print('\nDB connection not fully configured via environment variables.')
    DB_HOST = DB_HOST or input('DB host (default: localhost): ') or 'localhost'
    DB_USER = DB_USER or input('DB user (default: root): ') or 'root'
    if not DB_PASSWORD:
        DB_PASSWORD = input('DB password (leave blank for none): ')
    DB_NAME = DB_NAME or input('DB name (default: museum_db): ') or 'museum_db'


def migrate():
    try:
        # Connect to database
        db = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = db.cursor()
        
        print("\n🔄 Starting database migration...\n")
        
        # Check if columns already exist
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
            },
            {
                'name': 'ticket_code index',
                'sql': "CREATE INDEX idx_code ON tickets(ticket_code);",
                'check': "SHOW INDEX FROM tickets WHERE Key_name='idx_code'"
            }
        ]
        
        for migration in migrations:
            try:
                cursor.execute(migration['check'])
                if cursor.fetchone():
                    print(f"✅ {migration['name']} already exists - skipping")
                else:
                    cursor.execute(migration['sql'])
                    db.commit()
                    print(f"✅ Added {migration['name']}")
            except pymysql.err.ProgrammingError as e:
                # Index might not be checkable this way, just try to create
                try:
                    cursor.execute(migration['sql'])
                    db.commit()
                    print(f"✅ Added {migration['name']}")
                except Exception as ex:
                    if "already exists" in str(ex) or "Duplicate" in str(ex):
                        print(f"✅ {migration['name']} already exists - skipping")
                    else:
                        print(f"⚠️  Could not add {migration['name']}: {ex}")
        
        print("\n✅ Database migration completed successfully!\n")
        db.close()
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
        print("\nMake sure your database connection details are correct:")
        print(f"  DB_HOST: {DB_HOST}")
        print(f"  DB_USER: {DB_USER}")
        print(f"  DB_NAME: {DB_NAME}")


if __name__ == '__main__':
    # If env vars are not set, try to load from backend/app.py
    if not (DB_HOST and DB_USER and DB_NAME):
        parsed = try_load_from_app_py()
        if parsed:
            DB_HOST = DB_HOST or parsed.get('host') or ''
            DB_USER = DB_USER or parsed.get('user') or ''
            DB_PASSWORD = DB_PASSWORD or parsed.get('password') or ''
            DB_NAME = DB_NAME or parsed.get('database') or ''

    # If still missing, prompt interactively
    if not (DB_HOST and DB_USER and DB_NAME):
        get_db_config_interactive()

    migrate()
