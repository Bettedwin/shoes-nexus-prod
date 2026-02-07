from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Add size column
try:
    cur.execute("ALTER TABLE returns_exchanges ADD COLUMN size TEXT")
except Exception as e:
    print("Size column:", e)

# Add quantity column
try:
    cur.execute("ALTER TABLE returns_exchanges ADD COLUMN quantity INTEGER")
except Exception as e:
    print("Quantity column:", e)

conn.commit()
conn.close()

print("✅ returns_exchanges updated")
