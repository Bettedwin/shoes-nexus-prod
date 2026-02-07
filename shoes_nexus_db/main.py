from db_config import DB_PATH
import sqlite3

# ============================
# BOOTSTRAP / ONE-TIME SETUP
# ============================

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ----------------------------
# CREATE PRODUCTS TABLE
# ----------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    brand TEXT,
    model TEXT,
    color TEXT,
    buying_price INTEGER,
    selling_price INTEGER,
    stock INTEGER
)
""")

# ----------------------------
# RESET PRODUCTS (SAFE – SALES APPROVED TO RESET)
# ----------------------------
cursor.execute("DELETE FROM products")
cursor.execute("DELETE FROM sqlite_sequence WHERE name='products'")

# Force next AUTOINCREMENT ID to be 1001
cursor.execute("""
INSERT INTO sqlite_sequence (name, seq)
VALUES ('products', 1000)
""")

# ----------------------------
# FUNCTION TO ADD PRODUCT
# ----------------------------
def add_product(category, brand, model, color, buying_price, selling_price, stock):
    cursor.execute("""
        INSERT INTO products
        (category, brand, model, color, buying_price, selling_price, stock)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (category, brand, model, color, buying_price, selling_price, stock))
    conn.commit()
    print(f"✅ Added: {brand} {model} ({color})")

# ----------------------------
# SEED PRODUCTS (IDs WILL START AT 1001)
# ----------------------------
add_product("Men", "Hermes", "Sandals", "Black", 1384, 3500, 10)
add_product("Men", "Hermes", "Sandals", "Grey", 1384, 3500, 8)

add_product("Women", "Primark", "New 3-Strap", "Beige", 710, 2000, 12)
add_product("Women", "Primark", "New 3-Strap", "Black", 710, 2000, 15)
add_product("Women", "Primark", "New 3-Strap", "White", 710, 2000, 10)
add_product("Women", "Primark", "New 3-Strap", "Brown", 710, 2000, 10)
add_product("Women", "Primark", "Normal 3-Strap", "Brown", 710, 2000, 10)
add_product("Women", "Primark", "Normal 3-Strap", "Gold", 710, 2000, 10)
add_product("Women", "Primark", "Metal-Strap", "Brown", 710, 2000, 10)
add_product("Women", "Primark", "Diamond Strap", "Gold", 710, 2000, 10)
add_product("Women", "Primark", "Diamond Strap", "Green", 710, 2000, 10)
add_product("Women", "Primark", "Platform Slides", "White", 710, 2000, 10)
add_product("Women", "Primark", "Platform Slides", "Maroon", 710, 2000, 10)

add_product("Women", "Zara", "Multistrap", "White", 990, 2200, 9)
add_product("Women", "Zara", "Multistrap", "Black", 990, 2200, 11)
add_product("Women", "Zara", "Multistrap", "Suede-Brown", 990, 2200, 11)
add_product("Women", "Zara", "Multistrap", "Black-Glitter", 990, 2200, 11)
add_product("Women", "Zara", "Multistrap", "Silver", 990, 2200, 11)
add_product("Women", "Zara", "Multistrap", "Choc-Brown", 990, 2200, 11)
add_product("Women", "Zara", "Multistrap", "Crocodile-Brown", 990, 2200, 11)
add_product("Women", "Zara", "Slides", "White", 990, 2500, 11)

add_product("Women", "JM", "Slides", "Beige", 710, 1900, 12)
add_product("Women", "JM", "Slides", "Black", 710, 1900, 15)

add_product("Women", "Forever 21 Doll Shoes", "Doll Shoes", "Denim-Black", 710, 2300, 15)
add_product("Women", "Forever 21 Doll Shoes", "Doll Shoes", "Animal-Print", 710, 2300, 15)

add_product("Women", "Erynn-Paris Slides", "Slides", "Suede-Brown", 710, 2500, 10)
add_product("Women", "Erynn-Paris Slides", "Slides", "Pink-Orange", 710, 2500, 10)

add_product("Women", "Forever 21 Slides", "Leather Slides", "Brown", 710, 2000, 10)
add_product("Women", "Rock & Candy", "H-inspired Sandals", "Brown", 710, 2300, 10)
add_product("Women", "Forever 21", "Double Sole Slides", "Beige", 710, 2500, 10)
add_product("Women", "Masai", "Criss-Crossed Straps", "Black-White", 710, 2000, 10)

add_product("Women", "EGO", "Butterfly Heels", "Pink", 710, 2000, 10)
add_product("Women", "EGO", "Butterfly Heels", "Gold", 710, 2000, 10)
add_product("Women", "EGO", "Rhinestone Stilletos", "Silver", 710, 2000, 10)
add_product("Women", "EGO", "Rhinestone Stilletos", "Gold", 710, 2000, 10)
add_product("Women", "EGO", "Rhinestone Stilletos", "Black", 710, 2000, 10)

add_product("Women", "Fluffy", "Fluffy Sandals", "Yellow", 710, 2000, 10)

conn.close()

print("\n🎯 Initial inventory added successfully with IDs starting at 1001")
print("⚠️ Do NOT run this file again")
