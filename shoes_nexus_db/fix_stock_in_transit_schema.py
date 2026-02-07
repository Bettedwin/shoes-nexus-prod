from db_config import DB_PATH
# fix_stock_in_transit_schema.py
import sqlite3

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS stock_in_transit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    size TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    total_cost REAL NOT NULL,
    expected_date DATE,
    notes TEXT,
    entered_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()

print("✅ stock_in_transit schema fixed")
