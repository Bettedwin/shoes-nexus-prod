from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS returns_exchanges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    type TEXT CHECK(type IN ('EXCHANGE', 'RETURN')) NOT NULL,
    amount INTEGER DEFAULT 0,
    notes TEXT,
    initiated_by TEXT NOT NULL,
    approved_by TEXT,
    status TEXT CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED')) DEFAULT 'PENDING',
    created_at TEXT DEFAULT (date('now')),
    FOREIGN KEY (sale_id) REFERENCES sales(id)
)
""")

conn.commit()
conn.close()

print("✅ returns_exchanges table ready")
