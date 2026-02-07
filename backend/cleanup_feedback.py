import pymysql
import os

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'Ishwarya@123')
DB_NAME = os.getenv('DB_NAME', 'museum_db')

def cleanup_feedback():
    """Delete all feedback/reviews from the database"""
    try:
        db = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset='utf8mb4'
        )
        cursor = db.cursor()
        
        # Get count before deletion
        cursor.execute("SELECT COUNT(*) FROM feedback")
        count_before = cursor.fetchone()[0]
        print(f"📊 Feedback records before cleanup: {count_before}")
        
        # Delete all feedback
        cursor.execute("DELETE FROM feedback")
        db.commit()
        
        # Get count after deletion
        cursor.execute("SELECT COUNT(*) FROM feedback")
        count_after = cursor.fetchone()[0]
        print(f"✅ Feedback records after cleanup: {count_after}")
        print(f"🗑️  Deleted {count_before} feedback records")
        
        cursor.close()
        db.close()
        
    except pymysql.Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🧹 Starting feedback cleanup...")
    cleanup_feedback()
    print("✅ Cleanup complete!")
