from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("🔧 Fixing cost column data types...")

# Get all sales
cur.execute("SELECT id, cost FROM sales")
rows = cur.fetchall()

fixed_count = 0

for sale_id, cost in rows:
    # Convert bytes to integer
    if isinstance(cost, bytes):
        try:
            int_value = int.from_bytes(cost, byteorder='little')
            cur.execute("UPDATE sales SET cost = ? WHERE id = ?", (int_value, sale_id))
            fixed_count += 1
            print(f"✅ Fixed sale {sale_id}: bytes -> {int_value}")
        except Exception as e:
            print(f"❌ Error fixing sale {sale_id}: {e}")

conn.commit()
conn.close()

print(f"\n✅ Fixed {fixed_count} cost records")