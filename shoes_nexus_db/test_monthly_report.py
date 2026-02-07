from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

month = "2026-01"

print(f"\n📅 MONTHLY REPORT TEST - {month}\n")

# Get net sales data
cursor.execute("""
SELECT SUM(net_revenue), SUM(net_cost)
FROM net_sales
WHERE sale_date LIKE ?
""", (month + "%",))

revenue, cost = cursor.fetchone()

# Get expenses
cursor.execute("""
SELECT SUM(amount)
FROM daily_expenses
WHERE expense_date LIKE ?
""", (month + "%",))

expenses = cursor.fetchone()[0] or 0

# Fixed costs
rent = 35000
internet = 1500
power = 3000
fixed_costs = rent + internet + power

# Calculations
gross_profit = revenue - cost
net_profit = gross_profit - expenses - fixed_costs

print("="*50)
print(f"Month:           {month}")
print(f"Revenue:         KES {revenue:,.2f}")
print(f"Cost of Goods:   KES {cost:,.2f}")
print(f"Gross Profit:    KES {gross_profit:,.2f}")
print(f"Ads Spend:       KES {expenses:,.2f}")
print(f"Fixed Costs:     KES {fixed_costs:,.2f}")
print(f"NET PROFIT:      KES {net_profit:,.2f}")
print("="*50)

print("\n✅ This report now accounts for returns!")

conn.close()