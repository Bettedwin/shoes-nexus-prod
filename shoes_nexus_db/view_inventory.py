from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("SELECT * FROM products")
products = cursor.fetchall()

print("\n📦 SHOES NEXUS INVENTORY DASHBOARD\n")

print(f"{'ID':<3} {'Category':<8} {'Brand':<20} {'Model':<20} {'Color':<15} {'Buy':<8} {'Sell':<8} {'Stock':<6} {'Reorder'}")
print("-" * 110)

for p in products:
    id, category, brand, model, color, buy, sell, stock, reorder_level = p
    print(f"{id:<3} {category:<8} {brand:<20} {model:<20} {color:<15} {buy:<8} {sell:<8} {stock:<6} {reorder_level}")

conn.close()
