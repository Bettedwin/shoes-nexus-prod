from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Show all sales
cursor.execute("SELECT id, product_id, quantity, sale_date FROM sales ORDER BY id DESC LIMIT 10")
sales = cursor.fetchall()

print("📋 Recent Sales:")
print(f"{'Sale ID':<10} {'Product ID':<12} {'Quantity':<10} {'Date'}")
print("-" * 50)
for sale in sales:
    print(f"{sale[0]:<10} {sale[1]:<12} {sale[2]:<10} {sale[3]}")

print("\n")

# Show all return requests (handle None values)
cursor.execute("SELECT id, sale_id, quantity, status FROM returns_exchanges")
returns = cursor.fetchall()

print("📋 Return Requests:")
print(f"{'Return ID':<12} {'Sale ID':<10} {'Quantity':<10} {'Status'}")
print("-" * 50)
for ret in returns:
    ret_id = ret[0] if ret[0] is not None else "N/A"
    sale_id = ret[1] if ret[1] is not None else "N/A"
    qty = ret[2] if ret[2] is not None else "N/A"
    status = ret[3] if ret[3] is not None else "N/A"
    print(f"{str(ret_id):<12} {str(sale_id):<10} {str(qty):<10} {status}")

print("\n")

# Show sales with return information
cursor.execute("""
SELECT 
    id,
    product_id,
    quantity,
    COALESCE(returned_quantity, 0) AS returned,
    return_status,
    sale_date
FROM sales 
WHERE returned_quantity > 0 OR return_status != 'NONE'
ORDER BY id DESC
""")
returned_sales = cursor.fetchall()

print("📋 Sales with Returns:")
print(f"{'Sale ID':<10} {'Product':<10} {'Sold':<8} {'Returned':<10} {'Status':<10} {'Date'}")
print("-" * 70)
for sale in returned_sales:
    print(f"{sale[0]:<10} {sale[1]:<10} {sale[2]:<8} {sale[3]:<10} {sale[4]:<10} {sale[5]}")

conn.close()

print("\n✅ Check complete!")