from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    cursor.execute("""
        ALTER TABLE staff
        ADD COLUMN password_hash TEXT
    """)
    print("✅ password_hash column added successfully")
except sqlite3.OperationalError as e:
    print("ℹ️ Column already exists or skipped:", e)

conn.commit()
conn.close()
