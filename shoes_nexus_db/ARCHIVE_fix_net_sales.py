from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Drop broken view
cur.execute("DROP VIEW IF EXISTS net_sales")

# Recreate correct net_sales view
cur.execute("""
CREATE VIEW net_sales AS
SELECT
    s.id,
    s.product_id,
    s.size,
    s.sale_date,
    s.payment_method,
    s.notes,

    (s.quantity - COALESCE(s.returned_quantity, 0)) AS net_quantity,

    (s.revenue * (s.quantity - COALESCE(s.returned_quantity, 0)) / s.quantity) AS net_revenue,

    (s.cost * (s.quantity - COALESCE(s.returned_quantity, 0)) / s.quantity) AS net_cost

FROM sales s
WHERE s.return_status != 'FULL'
""")

conn.commit()

# Verify
rows = cur.execute("SELECT * FROM net_sales LIMIT 3").fetchall()
print("net_sales OK. Sample rows:")
for r in rows:
    print(r)

conn.close()
