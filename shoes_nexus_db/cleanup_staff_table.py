from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
CREATE TABLE staff_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password_hash TEXT,
    role TEXT
)
""")

cur.execute("""
INSERT INTO staff_new (id, username, password_hash, role)
SELECT id, username, password_hash, role FROM staff
""")

cur.execute("DROP TABLE staff")
cur.execute("ALTER TABLE staff_new RENAME TO staff")

conn.commit()
conn.close()

print("✅ Plain password column removed permanently")
