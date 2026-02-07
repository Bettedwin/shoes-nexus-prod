import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "shoes_nexus.db")

print("=" * 60)
print("🔍 DATABASE DIAGNOSTIC")
print("=" * 60)
print(f"\n📁 Database path: {DB_PATH}")
print(f"✅ Database exists: {os.path.exists(DB_PATH)}")

if not os.path.exists(DB_PATH):
    print("\n❌ DATABASE NOT FOUND!")
    print("Please check the path!")
    exit()

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Check tables
print("\n📊 TABLES IN DATABASE:")
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
for table in tables:
    print(f"  - {table[0]}")

# Check products
print("\n👟 PRODUCTS TABLE:")
try:
    cur.execute("SELECT COUNT(*) FROM products")
    total = cur.fetchone()[0]
    print(f"  Total products: {total}")
    
    cur.execute("SELECT COUNT(*) FROM products WHERE is_active = 1")
    active = cur.fetchone()[0]
    print(f"  Active products: {active}")
    
    if active > 0:
        print("\n📋 Sample products:")
        cur.execute("""
            SELECT id, brand, model, color, selling_price, is_active
            FROM products
            WHERE is_active = 1
            LIMIT 5
        """)
        
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]} {row[2]} ({row[3]}) - KES {row[4]} - Active: {row[5]}")
    else:
        print("\n⚠️  No active products found!")
        
except Exception as e:
    print(f"  ❌ Error: {e}")

# Check product_sizes
print("\n📏 PRODUCT SIZES TABLE:")
try:
    cur.execute("SELECT COUNT(*) FROM product_sizes")
    total_sizes = cur.fetchone()[0]
    print(f"  Total size entries: {total_sizes}")
    
    cur.execute("SELECT COUNT(*) FROM product_sizes WHERE quantity > 0")
    with_stock = cur.fetchone()[0]
    print(f"  Sizes with stock: {with_stock}")
    
    if with_stock > 0:
        print("\n📋 Sample sizes with stock:")
        cur.execute("""
            SELECT ps.product_id, p.brand, p.model, ps.size, ps.quantity
            FROM product_sizes ps
            JOIN products p ON p.id = ps.product_id
            WHERE ps.quantity > 0
            LIMIT 5
        """)
        
        for row in cur.fetchall():
            print(f"  Product {row[0]}: {row[1]} {row[2]} - Size {row[3]} - Stock: {row[4]}")
    else:
        print("\n⚠️  No sizes with stock!")
        
except Exception as e:
    print(f"  ❌ Error: {e}")

conn.close()

print("\n" + "=" * 60)
print("DIAGNOSIS COMPLETE")
print("=" * 60)