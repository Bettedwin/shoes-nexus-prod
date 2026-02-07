from db_config import DB_PATH
import sqlite3

# ============================================
# CREATE ACTIVITY LOG TABLE
# ============================================

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Create the activity_log table
cur.execute("""
    CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        reference_id INTEGER,
        role TEXT NOT NULL,
        username TEXT NOT NULL,
        message TEXT,
        timestamp TEXT DEFAULT (datetime('now', 'localtime'))
    )
""")

conn.commit()

# Verify table was created
cur.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name='activity_log'
""")

result = cur.fetchone()

if result:
    print("✅ activity_log table created successfully")
    
    # Show table structure
    cur.execute("PRAGMA table_info(activity_log)")
    columns = cur.fetchall()
    
    print("\n📋 Table Structure:")
    print(f"{'Column':<15} {'Type':<10} {'Not Null':<10} {'Default'}")
    print("-" * 60)
    for col in columns:
        col_name = col[1]
        col_type = col[2]
        not_null = "YES" if col[3] else "NO"
        default = col[4] if col[4] else "None"
        print(f"{col_name:<15} {col_type:<10} {not_null:<10} {default}")
    
    print("\n✅ Activity log is ready to use!")
else:
    print("❌ Failed to create activity_log table")

conn.close()