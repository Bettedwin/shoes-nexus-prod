from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS daily_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    mpesa_total INTEGER,
    cash_total INTEGER
)
""")

conn.commit()
conn.close()

print("✅ Daily payment summary table created")
