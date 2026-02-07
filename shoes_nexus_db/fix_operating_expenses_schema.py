from db_config import DB_PATH
# fix_operating_expenses_schema.py
import sqlite3

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Add created_by column if missing
cur.execute("""
ALTER TABLE operating_expenses
ADD COLUMN created_by TEXT
""")

conn.commit()
conn.close()

print("✅ operating_expenses schema updated (created_by added)")
