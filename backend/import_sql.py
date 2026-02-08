import os
import pymysql

def get_db_config():
    host = os.getenv('DB_HOST', 'localhost')
    user = os.getenv('DB_USER', 'root')
    password = os.getenv('DB_PASSWORD', 'Ishwarya@123')
    dbname = os.getenv('DB_NAME', 'museum_db')
    port = int(os.getenv('DB_PORT', '3306'))
    return host, user, password, dbname, port

def ensure_database(conn, dbname):
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{dbname}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    conn.commit()
    cur.close()

def import_sql_file(host, user, password, dbname, port, sql_path):
    conn = pymysql.connect(host=host, user=user, password=password, port=port, charset='utf8mb4')
    try:
        ensure_database(conn, dbname)
        conn.select_db(dbname)
        with open(sql_path, 'r', encoding='utf-8') as f:
            sql = f.read()

        # Naive split by semicolon; works for simple schema file
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        cur = conn.cursor()
        executed = 0
        for stmt in statements:
            try:
                cur.execute(stmt)
                executed += 1
            except Exception as e:
                print(f"[WARN] Failed to execute statement: {e}\nStatement snippet: {stmt[:120]}")
        conn.commit()
        cur.close()
        print(f"✅ Imported SQL file '{sql_path}' ({executed} statements executed)")
    finally:
        conn.close()

if __name__ == '__main__':
    host, user, password, dbname, port = get_db_config()
    sql_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'museum.sql')
    sql_path = os.path.abspath(sql_path)
    print(f"Using DB: host={host} port={port} user={user} db={dbname}")
    if not os.path.exists(sql_path):
        print(f"❌ SQL file not found at {sql_path}")
        raise SystemExit(1)
    import_sql_file(host, user, password, dbname, port, sql_path)
