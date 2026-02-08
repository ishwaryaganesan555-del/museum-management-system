#!/usr/bin/env python3
"""Fetch Railway MySQL connection details from environment"""
import os
import sys

# Railway auto-adds DATABASE_URL or individual vars
db_url = os.getenv('DATABASE_URL', '')
db_host = os.getenv('DB_HOST', 'not set')
db_user = os.getenv('DB_USER', 'not set')
db_password = os.getenv('DB_PASSWORD', 'not set')
db_name = os.getenv('DB_NAME', 'not set')
db_port = os.getenv('DB_PORT', '3306')

print("\n" + "="*60)
print("RAILWAY MYSQL CREDENTIALS")
print("="*60)

if db_url:
    print(f"\n📍 DATABASE_URL (full connection string):\n{db_url}\n")

print(f"DB_HOST:     {db_host}")
print(f"DB_PORT:     {db_port}")
print(f"DB_USER:     {db_user}")
print(f"DB_PASSWORD: {'***' + db_password[-4:] if db_password != 'not set' else 'not set'}")
print(f"DB_NAME:     {db_name}")

print("\n✅ Use these to:")
print("  1. Connect locally: mysql -h HOST -P PORT -u USER -pPASSWORD DATABASE")
print("  2. Or set in backend/.env for local testing")
print("  3. Or they're already set in Railway variables\n")
