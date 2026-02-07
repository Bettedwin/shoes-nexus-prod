from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("🔧 Fixing buying_price column in products...")

# Get all products
cur.execute("SELECT id, buying_price FROM products")
rows = cur.fetchall()

fixed_count = 0

for product_id, buying_price in rows:
    # Convert bytes to integer
    if isinstance(buying_price, bytes):
        try:
            int_value = int.from_bytes(buying_price, byteorder='little')
            cur.execute("UPDATE products SET buying_price = ? WHERE id = ?", (int_value, product_id))
            fixed_count += 1
            print(f"✅ Fixed product {product_id}: bytes -> {int_value}")
        except Exception as e:
            print(f"❌ Error fixing product {product_id}: {e}")

conn.commit()
conn.close()

print(f"\n✅ Fixed {fixed_count} buying_price records")