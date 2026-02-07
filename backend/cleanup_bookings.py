#!/usr/bin/env python3
"""
Script to remove old/test booking data from the database
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
    
    # Delete all bookings (tickets)
    cursor.execute('DELETE FROM tickets')
    db.commit()
    print('✓ All booking data has been deleted from the database')
    
    cursor.close()
    db.close()
except Exception as e:
    print(f'✗ Error: {e}')
