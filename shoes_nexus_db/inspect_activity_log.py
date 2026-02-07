from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(activity_log)")
columns = cursor.fetchall()

print("\n📋 activity_log columns:")
for col in columns:
    print(col)

conn.close()
