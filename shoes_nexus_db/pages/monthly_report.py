from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

month = input("Enter month (YYYY-MM): ")

cursor.execute("""
SELECT SUM(net_revenue), SUM(net_cost)
FROM net_sales
WHERE sale_date LIKE ?
""", (month + "%",))

revenue, cost = cursor.fetchone()

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

gross_profit = revenue - cost
net_profit = gross_profit - expenses - fixed_costs

print("\n📅 SHOES NEXUS MONTHLY REPORT")
print("-----------------------------")
print(f"Month: {month}")
print(f"Revenue:        KES {revenue}")
print(f"Cost of Goods:  KES {cost}")
print(f"Gross Profit:   KES {gross_profit}")
print(f"Ads Spend:      KES {expenses}")
print(f"Fixed Costs:    KES {fixed_costs}")
print(f"Net Profit:     KES {net_profit}")

print("\n✅ Report generated successfully.")
cursor.execute("""
SELECT 
    SUM(mpesa_total),
    SUM(cash_total)
FROM daily_payments
WHERE strftime('%Y-%m', date) = ?
""", (month,))
