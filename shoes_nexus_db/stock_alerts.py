from db_config import DB_PATH
import sqlite3
import pandas as pd

conn = sqlite3.connect(DB_PATH)

df = pd.read_sql("SELECT * FROM products", conn)

low_stock = df[df["stock"] <= df["reorder_level"]]

if low_stock.empty:
    print("✅ All stock levels healthy")
else:
    print("\n🚨 LOW STOCK ALERT — REORDER NOW\n")
    print(low_stock[["brand", "model", "color", "stock", "reorder_level"]])

conn.close()
