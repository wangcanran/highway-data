import sqlite3

db_path = r'D:\python_code\testwork\highway_db_20251120_163848.sqlite'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("=== Database Tables ===")
for table in tables:
    table_name = table[0]
    print(f"\n--- Table: {table_name} ---")
    
    # Get table schema
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    print("Columns:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    
    # Get row count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"Row count: {count}")
    
    # Get sample data
    if count > 0:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
        rows = cursor.fetchall()
        print(f"Sample data (first 3 rows):")
        for row in rows:
            print(f"  {row}")

conn.close()
