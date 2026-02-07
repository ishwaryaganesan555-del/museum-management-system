#!/usr/bin/env python3
"""
Script to remove old/test user data from the database
"""

import pymysql

try:
    # Connect to database
    db = pymysql.connect(
        host="localhost",
        user="root",
        password="Ishwarya@123",
        database="museum_db"
    )
    cursor = db.cursor()
    
    # Delete all non-admin users
    cursor.execute('DELETE FROM users WHERE role = "user"')
    db.commit()
    print('✓ All user data has been deleted from the database')
    print('✓ Admin users remain intact')
    
    cursor.close()
    db.close()
except Exception as e:
    print(f'✗ Error: {e}')
