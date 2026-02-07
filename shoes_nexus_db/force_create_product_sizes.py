from db_config import DB_PATH
import sqlite3
import os

DB_PATH = os.path.abspath(DB_PATH)
print("📁 Using database:", DB_PATH)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS product_sizes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    size TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    UNIQUE(product_id, size),
    FOREIGN KEY(product_id) REFERENCES products(id)
)
""")

conn.commit()

# Verify table exists
tables = cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()

conn.close()

print("📋 Tables in DB:")
for t in tables:
    print(" -", t[0])

print("✅ product_sizes table ensured")
