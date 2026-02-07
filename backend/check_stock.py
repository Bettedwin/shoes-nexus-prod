import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "shoes_nexus.db")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("📊 STOCK VERIFICATION")
print("=" * 60)

# Get sample of products with stock
cur.execute("""
    SELECT 
        p.brand,
        p.model,
        p.color,
        ps.size,
        ps.quantity
    FROM product_sizes ps
    JOIN products p ON p.id = ps.product_id
    WHERE ps.quantity > 0
    ORDER BY p.brand, p.model, ps.size
    LIMIT 20
""")

print(f"\n{'Brand':<15} {'Model':<20} {'Color':<12} {'Size':<6} {'Stock'}")
print("-" * 60)

for row in cur.fetchall():
    brand, model, color, size, qty = row
    print(f"{brand:<15} {model:<20} {color:<12} {size:<6} {qty}")

# Get totals
cur.execute("SELECT COUNT(*) FROM product_sizes WHERE quantity > 0")
total = cur.fetchone()[0]

print("\n" + "=" * 60)
print(f"✅ Total size variants in stock: {total}")

conn.close()