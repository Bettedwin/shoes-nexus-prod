from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
ALTER TABLE sales
ADD COLUMN size TEXT
""")

conn.commit()
conn.close()

print("✅ size column added to sales table")
