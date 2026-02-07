import sqlite3
import os

# Connect to database
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "shoes_nexus.db")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("📦 STOCK UPDATE TOOL")
print("=" * 50)

# First, let's check if product_sizes table exists
try:
    cur.execute("SELECT COUNT(*) FROM product_sizes")
    print(f"✅ product_sizes table exists")
except sqlite3.OperationalError:
    print("❌ product_sizes table doesn't exist. Creating it...")
    cur.execute("""
        CREATE TABLE product_sizes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            size TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            UNIQUE(product_id, size),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)
    conn.commit()
    print("✅ Table created!")

# Get all products
cur.execute("""
    SELECT id, brand, model, color, category
    FROM products
    WHERE is_active = 1
    ORDER BY brand, model
""")

products = cur.fetchall()

print(f"\n✅ Found {len(products)} products")
print("\nUpdating stock for all products...\n")

# Common sizes for women's shoes
women_sizes = ['37', '38', '39', '40', '41']

# Common sizes for men's shoes
men_sizes = ['40', '41', '42', '43', '44', '45']

for product in products:
    product_id, brand, model, color, category = product
    
    # Determine sizes based on category
    if category and category.lower() == 'men':
        sizes = men_sizes
    else:
        sizes = women_sizes
    
    # Add stock for each size
    for size in sizes:
        try:
            # Try to insert new record
            cur.execute("""
                INSERT INTO product_sizes (product_id, size, quantity)
                VALUES (?, ?, ?)
            """, (product_id, size, 10))
            
        except sqlite3.IntegrityError:
            # Record exists, update it instead
            cur.execute("""
                UPDATE product_sizes
                SET quantity = 10
                WHERE product_id = ? AND size = ?
            """, (product_id, size))
    
    print(f"  ✅ {brand} {model} ({color}) - {category or 'Women'} - Sizes: {', '.join(sizes)}")

conn.commit()

# Verify the update
cur.execute("SELECT COUNT(*) FROM product_sizes WHERE quantity > 0")
total_sizes = cur.fetchone()[0]

conn.close()

print("\n" + "=" * 50)
print("✅ Stock update complete!")
print(f"📦 Total size variants with stock: {total_sizes}")
print("\n💡 Next steps:")
print("   1. Restart your backend (if running)")
print("   2. Refresh your website")
print("   3. Products should now show as available!")
print("\n🔗 Test at: http://localhost:8000/api/products")