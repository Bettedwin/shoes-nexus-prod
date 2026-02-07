from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
ALTER TABLE products ADD COLUMN reorder_level INTEGER DEFAULT 10
""")

conn.commit()
conn.close()

print("✅ Reorder level column added successfully.")
