from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("🔍 RETURNS IMPACT VERIFICATION\n")

# Get a sale that has returns
cur.execute("""
SELECT 
    s.id,
    s.quantity,
    s.returned_quantity,
    s.return_status,
    s.revenue,
    s.cost
FROM sales s
WHERE s.returned_quantity > 0
LIMIT 1
""")

sale = cur.fetchone()

if not sale:
    print("ℹ️  No returned sales found yet")
else:
    sale_id, qty, returned, status, revenue, cost = sale
    
    print(f"📋 Sample Returned Sale (ID: {sale_id})")
    print(f"   Original Quantity: {qty}")
    print(f"   Returned Quantity: {returned}")
    print(f"   Return Status: {status}")
    print(f"   Original Revenue: KES {revenue}")
    print(f"   Original Cost: KES {cost}")
    
    # Check net_sales view
    cur.execute("""
    SELECT net_quantity, net_revenue, net_cost
    FROM net_sales
    WHERE sale_id = ?
    """, (sale_id,))
    
    net = cur.fetchone()
    
    if net:
        net_qty, net_rev, net_cost = net
        print(f"\n   Net Quantity: {net_qty}")
        print(f"   Net Revenue: KES {net_rev:.2f}")
        print(f"   Net Cost: KES {net_cost:.2f}")
        print(f"   Net Profit: KES {net_rev - net_cost:.2f}")
    else:
        print("\n   ⚠️  Not in net_sales view (fully returned)")

print("\n" + "="*50)

# Monthly comparison
cur.execute("""
SELECT 
    strftime('%Y-%m', sale_date) AS month,
    SUM(revenue) AS gross_revenue,
    SUM(cost) AS gross_cost,
    COUNT(*) AS total_sales
FROM sales
GROUP BY month
ORDER BY month DESC
LIMIT 3
""")

print("\n📊 GROSS SALES (from sales table - includes returns)")
print(f"{'Month':<10} {'Revenue':<15} {'Cost':<15} {'Sales'}")
print("-" * 55)
for row in cur.fetchall():
    print(f"{row[0]:<10} KES {row[1]:<12} KES {row[2]:<12} {row[3]}")

cur.execute("""
SELECT 
    strftime('%Y-%m', sale_date) AS month,
    SUM(net_revenue) AS net_revenue,
    SUM(net_cost) AS net_cost,
    COUNT(*) AS net_sales
FROM net_sales
GROUP BY month
ORDER BY month DESC
LIMIT 3
""")

print("\n📊 NET SALES (from net_sales view - excludes returns)")
print(f"{'Month':<10} {'Revenue':<15} {'Cost':<15} {'Sales'}")
print("-" * 55)
for row in cur.fetchall():
    print(f"{row[0]:<10} KES {row[1]:<12.2f} KES {row[2]:<12.2f} {row[3]}")

conn.close()

print("\n✅ Verification complete!")