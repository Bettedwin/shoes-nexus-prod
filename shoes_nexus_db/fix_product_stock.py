from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("🔧 Fixing stock column in products table...")

# Get all products
cur.execute("SELECT id, stock FROM products")
rows = cur.fetchall()

fixed_count = 0

for product_id, stock in rows:
    # Convert bytes to integer
    if isinstance(stock, bytes):
        try:
            int_value = int.from_bytes(stock, byteorder='little')
            cur.execute("UPDATE products SET stock = ? WHERE id = ?", (int_value, product_id))
            fixed_count += 1
            print(f"✅ Fixed product {product_id}: bytes -> {int_value}")
        except Exception as e:
            print(f"❌ Error fixing product {product_id}: {e}")
    elif stock is None:
        # Set to 0 if NULL
        cur.execute("UPDATE products SET stock = 0 WHERE id = ?", (product_id,))
        fixed_count += 1
        print(f"✅ Fixed product {product_id}: NULL -> 0")

conn.commit()
conn.close()

print(f"\n✅ Fixed {fixed_count} product stock records")