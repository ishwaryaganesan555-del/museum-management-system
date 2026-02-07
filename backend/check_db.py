import pymysql

# Connect to database
db = pymysql.connect(
    host="localhost",
    user="root",
    password="Ishwarya@123",
    database="museum_db"
)
cursor = db.cursor()

# Get table structure
cursor.execute("DESCRIBE tickets")
result = cursor.fetchall()

print("\n=== TICKETS TABLE STRUCTURE ===\n")
print(f"{'Field':<20} {'Type':<20} {'Null':<10} {'Key':<10} {'Default':<15} {'Extra'}")
print("-" * 90)
for row in result:
    print(f"{row[0]:<20} {row[1]:<20} {row[2]:<10} {str(row[3]):<10} {str(row[4]):<15} {row[5]}")

db.close()
print("\n")
