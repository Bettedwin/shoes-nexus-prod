from db_config import DB_PATH
import sqlite3

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
conn.close()

print("✅ product_sizes table created successfully")
