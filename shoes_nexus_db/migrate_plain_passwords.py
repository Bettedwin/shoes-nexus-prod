from db_config import DB_PATH
import sqlite3
import hashlib

def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT id, password FROM staff WHERE password_hash IS NULL")
users = cur.fetchall()

for user_id, password in users:
    cur.execute(
        "UPDATE staff SET password_hash=? WHERE id=?",
        (hash_password(password), user_id)
    )

conn.commit()
conn.close()

print("✅ Existing users migrated to password_hash")
