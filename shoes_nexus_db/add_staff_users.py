from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

users = [
    ("admin", "admin123", "Admin"),
    ("manager", "manager123", "Manager"),
    ("cashier", "cash123", "Cashier"),
]

for username, password, role in users:
    try:
        cursor.execute(
            "INSERT INTO staff (username, password, role) VALUES (?, ?, ?)",
            (username, password, role)
        )
        print(f"✅ {role} user '{username}' added")
    except sqlite3.IntegrityError:
        print(f"ℹ️ User '{username}' already exists — skipped")

conn.commit()
conn.close()

print("✅ Staff user setup complete.")
