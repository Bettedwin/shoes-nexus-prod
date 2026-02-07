from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Add payment_method column if missing
try:
    cursor.execute("ALTER TABLE sales ADD COLUMN payment_method TEXT")
    print("✅ payment_method column added to sales table")
except sqlite3.OperationalError:
    print("ℹ️ payment_method column already exists")

conn.commit()
conn.close()
