from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Read all products
cursor.execute("SELECT id, stock FROM products")
rows = cursor.fetchall()

for row in rows:
    product_id, stock = row

    # If stock is bytes, convert it to integer
    if isinstance(stock, bytes):
        stock_int = int.from_bytes(stock, byteorder="little")
        cursor.execute("UPDATE products SET stock=? WHERE id=?", (stock_int, product_id))

conn.commit()
conn.close()

print("✅ Stock column fixed and converted to integers")
