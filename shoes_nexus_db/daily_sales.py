from db_config import DB_PATH
import sqlite3
from datetime import datetime

# Connect to database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

today = datetime.now().strftime("%Y-%m-%d")

print("\n🛒 SHOES NEXUS DAILY SALES ENTRY\n")

# Fetch products
cursor.execute("SELECT id, brand, model, color, selling_price, buying_price, stock FROM products")
products = cursor.fetchall()

print(f"{'ID':<3} {'Brand':<18} {'Model':<20} {'Color':<15} {'Sell(KES)':<10} {'Stock'}")
print("-" * 85)

for p in products:
    print(f"{p[0]:<3} {p[1]:<18} {p[2]:<20} {p[3]:<15} {p[4]:<10} {p[6]}")

daily_revenue = 0
daily_cost = 0
mpesa_total = 0
cash_total = 0

# Sales entry loop
while True:
    product_id = input("\nEnter Product ID sold (or 'done'): ")

    if product_id.lower() == "done":
        break

    quantity = int(input("Enter quantity sold: "))
    payment_method = input("Payment method (MPESA/CASH): ").upper()

    if payment_method not in ["MPESA", "CASH"]:
        print("❌ Invalid payment method. Use MPESA or CASH.")
        continue

    cursor.execute("SELECT selling_price, buying_price, stock FROM products WHERE id=?", (product_id,))
    product = cursor.fetchone()

    if not product:
        print("❌ Invalid product ID")
        continue

    selling_price, buying_price, stock = product

    if quantity > stock:
        print("❌ Not enough stock available!")
        continue

    revenue = selling_price * quantity
    cost = buying_price * quantity

    daily_revenue += revenue
    daily_cost += cost

    if payment_method == "MPESA":
        mpesa_total += revenue
    else:
        cash_total += revenue

    new_stock = stock - quantity
    cursor.execute("UPDATE products SET stock=? WHERE id=?", (new_stock, product_id))

    cursor.execute("""
        INSERT INTO sales (product_id, quantity, revenue, cost, payment_method, sale_date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (product_id, quantity, revenue, cost, payment_method, today))

    conn.commit()

    print(f"✅ Sold {quantity} units | Revenue: KES {revenue} | {payment_method}")

# Daily ads expense
ads_spend = int(input("\nEnter today's ads spend (KES): "))

cursor.execute("""
    INSERT INTO daily_expenses (amount, description, expense_date)
    VALUES (?, ?, ?)
""", (ads_spend, "Ads Spend", today))

conn.commit()

# Save daily payment summary
cursor.execute("""
    INSERT INTO daily_payments (date, mpesa_total, cash_total)
    VALUES (?, ?, ?)
""", (today, mpesa_total, cash_total))

conn.commit()

# Profit calculations
gross_profit = daily_revenue - daily_cost
net_profit = gross_profit - ads_spend

# Daily summary
print("\n📊 DAILY BUSINESS SUMMARY")
print("-------------------------")
print(f"Revenue:      KES {daily_revenue}")
print(f"Cost:         KES {daily_cost}")
print(f"Gross Profit: KES {gross_profit}")
print(f"Ads Spend:    KES {ads_spend}")
print(f"Net Profit:   KES {net_profit}")
print(f"MPESA Total:  KES {mpesa_total}")
print(f"Cash Total:   KES {cash_total}")
print("\nℹ️  Note: Returns will adjust these figures in reports")

print("\n✅ Day closed and saved successfully.")

conn.close()
