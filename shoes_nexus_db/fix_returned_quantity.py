from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("🔧 Fixing returned_quantity data types...")

# Get all sales with returned_quantity
cur.execute("SELECT id, returned_quantity FROM sales WHERE returned_quantity IS NOT NULL")
rows = cur.fetchall()

fixed_count = 0

for sale_id, returned_qty in rows:
    # Convert to integer if it's bytes or string
    if isinstance(returned_qty, (bytes, str)):
        try:
            if isinstance(returned_qty, bytes):
                int_value = int.from_bytes(returned_qty, byteorder='little')
            else:
                int_value = int(returned_qty)
            
            cur.execute("UPDATE sales SET returned_quantity = ? WHERE id = ?", (int_value, sale_id))
            fixed_count += 1
            print(f"✅ Fixed sale {sale_id}: {returned_qty} -> {int_value}")
        except Exception as e:
            print(f"❌ Error fixing sale {sale_id}: {e}")

conn.commit()
conn.close()

print(f"\n✅ Fixed {fixed_count} records")