from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE sales ADD COLUMN notes TEXT")
    print("✅ Sales notes column added successfully")
except sqlite3.OperationalError:
    print("ℹ️ Notes column already exists")

conn.commit()
conn.close()
