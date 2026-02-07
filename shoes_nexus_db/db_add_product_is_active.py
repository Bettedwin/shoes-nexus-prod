from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

try:
    cur.execute(
        "ALTER TABLE products ADD COLUMN is_active INTEGER DEFAULT 1"
    )
    print("✅ is_active column added")
except sqlite3.OperationalError:
    print("ℹ️ is_active column already exists")

conn.commit()
conn.close()
