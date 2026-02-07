from db_config import DB_PATH
import sqlite3

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("DROP VIEW IF EXISTS net_sales")

cur.execute("""
CREATE VIEW net_sales AS
SELECT
    s.id AS sale_id,
    s.product_id,
    s.size,
    (s.quantity - COALESCE(s.returned_quantity, 0)) AS net_quantity,
    CASE
        WHEN s.quantity = 0 THEN 0
        ELSE s.revenue * (s.quantity - COALESCE(s.returned_quantity, 0)) / s.quantity
    END AS net_revenue,
    CASE
        WHEN s.quantity = 0 THEN 0
        ELSE s.cost * (s.quantity - COALESCE(s.returned_quantity, 0)) / s.quantity
    END AS net_cost,
    s.payment_method,
    s.sale_date
FROM sales s
WHERE s.return_status != 'FULL';
""")

conn.commit()
conn.close()

print("✅ net_sales view rebuilt correctly")
