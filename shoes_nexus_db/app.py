from db_config import DB_PATH
import streamlit as st
import sqlite3
import time
import pandas as pd

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# ----------------------------
# CONFIG
# ----------------------------
SESSION_TIMEOUT = 15 * 60  # 15 minutes
# ============================================
# ----------------------------
# DATABASE CONNECTION
# ----------------------------
def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)
#Ensure stock in transit table 
def ensure_stock_in_transit_table():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_in_transit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            size TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_cost REAL NOT NULL,
            expected_date DATE,
            notes TEXT,
            created_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
#ensure net sales view
def ensure_net_sales_view():
    conn = get_db()
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
        s.source,
        s.sale_date
    FROM sales s
    WHERE s.return_status != 'FULL';
    """)

    conn.commit()
    conn.close()

#Upgrade stock in transit table
def upgrade_stock_in_transit_table():
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("ALTER TABLE stock_in_transit ADD COLUMN expected_date DATE")
    except sqlite3.OperationalError:
        pass

    try:
        cur.execute("ALTER TABLE stock_in_transit ADD COLUMN notes TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

#Ensure opening inventory table
def ensure_opening_inventory_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS opening_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date DATE NOT NULL,
            total_value REAL NOT NULL,
            created_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

#Operating expenses table 
def ensure_operating_expenses_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS operating_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date DATE NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            created_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def ensure_sales_source_column():
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE sales ADD COLUMN source TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def ensure_product_public_fields():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(products)")
    columns = [row[1] for row in cur.fetchall()]
    if "image_url" not in columns:
        cur.execute("ALTER TABLE products ADD COLUMN image_url TEXT")
    if "public_brand" not in columns:
        cur.execute("ALTER TABLE products ADD COLUMN public_brand TEXT")
    if "public_title" not in columns:
        cur.execute("ALTER TABLE products ADD COLUMN public_title TEXT")
    if "public_description" not in columns:
        cur.execute("ALTER TABLE products ADD COLUMN public_description TEXT")
    conn.commit()
    conn.close()

def ensure_home_expenses_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS home_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date DATE NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

#return/exchange activity log
# ----------------------------
# ACTIVITY LOG (AUDIT TRAIL)
# ----------------------------
def ensure_activity_log():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            reference_id INTEGER,
            role TEXT,
            username TEXT,
            message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# ----------------------------
# SESSION MANAGEMENT
# ----------------------------
def init_session():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "role" not in st.session_state:
        st.session_state.role = None
    if "username" not in st.session_state:
        st.session_state.username = None
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = time.time()

def update_activity():
    st.session_state.last_activity = time.time()

def auto_logout():
    if time.time() - st.session_state.last_activity > SESSION_TIMEOUT:
        st.session_state.clear()
        st.warning("Session expired. Please log in again.")
        st.stop()

# ----------------------------
# AUTHENTICATION
# ----------------------------
from security import verify_password

def login_screen():
    st.title("👟 Shoes Nexus Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT password_hash, role FROM staff WHERE username=?",
            (username,),
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            stored_hash, role = user

            if verify_password(password, stored_hash):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = role
                update_activity()
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid username or password")
        else:
            st.error("Invalid username or password")

def sync_product_stock(cur, product_id):
    cur.execute(
        """
        SELECT COALESCE(SUM(quantity), 0)
        FROM product_sizes
        WHERE product_id = ?
        """,
        (product_id,)
    )

    total_stock = cur.fetchone()[0]

    cur.execute(
        """
        UPDATE products
        SET stock = ?
        WHERE id = ?
        """,
        (total_stock, product_id)
    )

  
# ----------------------------
# POS LOGIC
# ----------------------------
def pos_screen(show_prices=False):
    update_activity()
    st.subheader("🧾 Shoes Nexus POS")

    conn = get_db()

    # ----------------------------
    # LOAD PRODUCTS
    # ----------------------------
    products_df = pd.read_sql(
        """SELECT id, brand, model, color, selling_price, buying_price
        FROM products
        WHERE is_active = 1""",
        conn
    )

    if products_df.empty:
        st.warning("No products available.")
        conn.close()
        return

    products_df["display"] = (
        products_df["brand"] + " " +
        products_df["model"] + " (" +
        products_df["color"] + ")"
    )

    product_map = dict(zip(products_df["display"], products_df["id"]))

    selected_product = st.selectbox(
        "Select Product",
        product_map.keys()
    )

    product_id = product_map[selected_product]
    product = products_df[products_df["id"] == product_id].iloc[0]

    sell_price = int(product["selling_price"])
    buy_price = product["buying_price"]

    # ----------------------------
    # LOAD SIZES
    # ----------------------------
    sizes_df = pd.read_sql(
    """
    SELECT size, quantity
    FROM product_sizes
    WHERE product_id = ?
    ORDER BY size
    """,
    conn,
    params=(product_id,)
    )

    # 🧼 Remove zero-stock sizes
    sizes_df = sizes_df[sizes_df["quantity"] > 0]

    if sizes_df.empty:
        st.info("ℹ️ This product is SOLD OUT.")
        conn.close()
        return


    size_options = ["— Select size —"] + sizes_df["size"].astype(str).tolist()

    size = st.selectbox("Select Size", size_options)

    quantity = st.number_input(
        "Quantity",
        min_value=0,
        step=1,
        key="pos_quantity"
    )

    payment = st.radio(
        "Payment Method",
        ["CASH", "MPESA"],
        horizontal=True
    )

    source = st.selectbox(
        "Customer Source",
        [
            "In-store Walkins",
            "Instagram",
            "TikTok",
            "Twitter",
            "Website",
            "Referral",
            "Other"
        ]
    )

    notes = st.text_area("📝 Sales Notes (optional)")

    if show_prices:
        st.caption(f"Selling price: KES {sell_price}")

    sell_clicked = st.button("💰 SELL")

    # ==========================================================
    # SELL LOGIC — IMPOSSIBLE TO BYPASS
    # ==========================================================
    if sell_clicked:

        error = False

        if size == "— Select size —":
            st.error("❌ Please select a size.")
            error = True

        if quantity <= 0:
            st.error("❌ Quantity must be greater than 0.")
            error = True

        row = sizes_df[sizes_df["size"].astype(str) == size]

        if row.empty:
            st.error(f"❌ No stock found for size {size}.")
            error = True
        else:
            size_stock = int(row["quantity"].iloc[0])
            if quantity > size_stock:
                st.error(f"❌ Only {size_stock} pairs available for size {size}.")
                error = True

        # ----------------------------
        # EXECUTE SALE (ONLY IF VALID)
        # ----------------------------
        if not error:
            revenue = quantity * sell_price
            cost = (buy_price or 0) * quantity

            cur = conn.cursor()
            # 🔒 SAFETY CHECK: product still active
            cur.execute(
                "SELECT is_active FROM products WHERE id = ?",
                (product_id,)
            )
            if cur.fetchone()[0] != 1:
                st.error("❌ This product is no longer active and cannot be sold.")
                conn.close()
                return

            # Deduct size stock
            cur.execute(
                """
                UPDATE product_sizes
                SET quantity = quantity - ?
                WHERE product_id = ? AND size = ?
                """,
                (quantity, product_id, size)
            )

            # Sync main product stock
            sync_product_stock(cur, product_id)

            # Record sale
            cur.execute(
                """
                INSERT INTO sales
                (product_id, size, quantity, revenue, cost, payment_method, source, sale_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, date('now'), ?)
                """,
                (
                    product_id,
                    size,
                    quantity,
                    revenue,
                    cost,
                    payment,
                    source,
                    notes
                )
            )

            conn.commit()

            st.success("✅ Sale completed successfully!")
            st.write(f"🥿 Product: {selected_product}")
            st.write(f"📏 Size: {size}")
            st.write(f"📦 Quantity: {quantity}")
            st.write(f"💰 Revenue: KES {revenue}")
            st.balloons()

    conn.close()

def get_size_inventory():
    conn = get_db()
    df = pd.read_sql(
        """
        SELECT 
            p.id AS product_id,
            p.brand,
            p.model,
            p.color,
            ps.size,
            ps.quantity
        FROM product_sizes ps
        JOIN products p ON p.id = ps.product_id
        ORDER BY p.id, ps.size
        """,
        conn
    )
    conn.close()
    return df

# ----------------------------
# INVENTORY VIEW
#size stock alerts
def size_stock_alerts(role, threshold=2):
    st.subheader("🚨 Low Stock Alerts (By Size)")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            p.brand,
            p.model,
            p.color,
            ps.size,
            ps.quantity
        FROM product_sizes ps
        JOIN products p ON p.id = ps.product_id
        WHERE ps.quantity <= ?
        ORDER BY ps.quantity ASC
        """,
        conn,
        params=(threshold,)
    )
    conn.close()

    if df.empty:
        st.success("All size stocks are healthy ✅")
        return

    st.warning(f"⚠️ Sizes with stock ≤ {threshold}")

    if role == "Cashier":
        view = df[["brand", "model", "color", "size", "quantity"]]
    else:
        view = df

    st.dataframe(
        view,
        hide_index=True,
        use_container_width=True
    )

#zero size stock alerts
def zero_size_stock_alerts(role):
    st.subheader("⛔ Out-of-Stock Sizes")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            p.brand,
            p.model,
            p.color,
            ps.size,
            ps.quantity
        FROM product_sizes ps
        JOIN products p ON p.id = ps.product_id
        WHERE ps.quantity = 0
        ORDER BY p.brand, p.model, ps.size
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.success("No out-of-stock sizes 🎉")
        return

    st.error("⛔ These sizes are OUT OF STOCK")

    if role == "Cashier":
        view = df[["brand", "model", "color", "size"]]
    else:
        view = df

    st.dataframe(
        view,
        hide_index=True,
        use_container_width=True
    )

#most sold sizes per product
def most_sold_sizes_per_product():
    st.subheader("📊 Most Sold Sizes per Product")

    conn = get_db()

    df = pd.read_sql(
        """
        SELECT
            p.id AS product_id,
            p.brand,
            p.model,
            p.color,
            s.size,
            SUM(s.net_quantity) AS total_sold
        FROM net_sales s
        JOIN products p ON p.id = s.product_id
        GROUP BY
            p.id,
            p.brand,
            p.model,
            p.color,
            s.size
        ORDER BY
            p.brand,
            p.model,
            total_sold DESC
        """,
        conn
    )

    conn.close()

    if df.empty:
        st.info("No sales data available yet.")
        return

    # Group by product
    grouped = df.groupby(["product_id", "brand", "model", "color"])

    for (pid, brand, model, color), group in grouped:
        with st.expander(f"👟 {brand} {model} ({color})", expanded=False):

            view = group[["size", "total_sold"]].copy()
            view["total_sold"] = view["total_sold"].astype(int)

            st.dataframe(
                view,
                hide_index=True,
                use_container_width=True
            )

#most sold sizes by gender
def most_sold_sizes_by_gender():
    st.subheader("📊 Overall Most Sold Sizes (Men vs Women)")

    conn = get_db()

    df = pd.read_sql(
        """
        SELECT
            p.category,
            s.size,
            SUM(s.net_quantity) AS total_sold
        FROM net_sales s
        JOIN products p ON p.id = s.product_id
        WHERE p.category IS NOT NULL
        GROUP BY
            p.category,
            s.size
        ORDER BY
            p.category,
            total_sold DESC
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.info("No sales data available yet.")
        return

    df["total_sold"] = df["total_sold"].astype(int)
    df["category"] = df["category"].str.capitalize()

    col1, col2 = st.columns(2)

    # ---------------- MEN ----------------
    with col1:
        st.markdown("### 👨 Men — Most Sold Sizes")
        men = df[df["category"] == "Men"]

        if men.empty:
            st.info("No men sales recorded.")
        else:
            st.dataframe(
                men[["size", "total_sold"]],
                hide_index=True,
                use_container_width=True
            )

    # ---------------- WOMEN ----------------
    with col2:
        st.markdown("### 👩 Women — Most Sold Sizes")
        women = df[df["category"] == "Women"]

        if women.empty:
            st.info("No women sales recorded.")
        else:
            st.dataframe(
                women[["size", "total_sold"]],
                hide_index=True,
                use_container_width=True
            )

#dead stock - recommended for discounts
def dead_sizes_alerts():
    st.subheader("🧊 Dead Sizes Alert (No Sales Recorded)")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            p.brand,
            p.model,
            p.color,
            ps.size,
            ps.quantity AS current_stock,
            COALESCE(SUM(s.quantity - COALESCE(s.returned_quantity, 0)), 0) AS sold_qty
        FROM product_sizes ps
        JOIN products p ON p.id = ps.product_id
        LEFT JOIN sales s
            ON s.product_id = ps.product_id
            AND s.size = ps.size
        GROUP BY p.id, ps.size
        HAVING current_stock > 0 AND sold_qty = 0
        ORDER BY p.brand, p.model, ps.size
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.success("✅ No dead sizes detected")
        return

    st.warning("⚠️ These sizes have stock but ZERO sales")

    st.dataframe(
        df.rename(columns={
            "brand": "Brand",
            "model": "Model",
            "color": "Color",
            "size": "Size",
            "current_stock": "Stock",
            "sold_qty": "Sold Qty"
        }),
        hide_index=True,
        use_container_width=True
    )

    #slow sizes alerts
def slow_sizes_alerts(threshold=5, days=30):
    st.subheader("🐢 Slow Sizes Alert (Low Movement)")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            p.brand,
            p.model,
            p.color,
            ps.size,
            ps.quantity AS current_stock,
            COALESCE(SUM(s.quantity - COALESCE(s.returned_quantity, 0)), 0) AS sold_qty
        FROM product_sizes ps
        JOIN products p ON p.id = ps.product_id
        LEFT JOIN sales s
            ON s.product_id = ps.product_id
            AND s.size = ps.size
            AND s.sale_date >= date('now', ?)
        GROUP BY p.id, ps.size
        HAVING current_stock > 0 AND sold_qty <= ?
        ORDER BY sold_qty ASC, p.brand, p.model, ps.size
        """,
        conn,
        params=(f"-{days} days", threshold)
    )
    conn.close()

    if df.empty:
        st.success("✅ No slow sizes detected")
        return

    st.warning(
        f"⚠️ Sizes sold ≤ {threshold} unit(s) in the last {days} days"
    )

    st.dataframe(
        df.rename(columns={
            "brand": "Brand",
            "model": "Model",
            "color": "Color",
            "size": "Size",
            "current_stock": "Stock",
            "sold_qty": "Sold (Last 30 Days)"
        }),
        hide_index=True,
        use_container_width=True
    )

#discount suggestions
def discount_suggestions(days_slow=30, days_dead=60):
    st.subheader("💸 Discount Suggestions (Slow & Dead Sizes)")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            p.brand,
            p.model,
            p.color,
            ps.size,
            ps.quantity AS current_stock,

            COALESCE(SUM(
                CASE 
                    WHEN s.sale_date >= date('now', ?) THEN (s.quantity - COALESCE(s.returned_quantity, 0))
                    ELSE 0
                END
            ), 0) AS sold_30,

            COALESCE(SUM(
                CASE 
                    WHEN s.sale_date >= date('now', ?) THEN (s.quantity - COALESCE(s.returned_quantity, 0))
                    ELSE 0
                END
            ), 0) AS sold_60

        FROM product_sizes ps
        JOIN products p ON p.id = ps.product_id
        LEFT JOIN sales s
            ON s.product_id = ps.product_id
            AND s.size = ps.size
        GROUP BY p.id, ps.size
        HAVING current_stock > 0
        """,
        conn,
        params=(f"-{days_slow} days", f"-{days_dead} days")
    )
    conn.close()

    if df.empty:
        st.success("✅ No discount suggestions available")
        return

    def classify(row):
        if row["sold_60"] == 0:
            return "DEAD", "30–50%"
        elif row["sold_30"] <= 2:
            return "SLOW", "10–20%"
        return None, None

    df[["Status", "Suggested Discount"]] = df.apply(
        lambda r: pd.Series(classify(r)),
        axis=1
    )

    df = df[df["Status"].notna()]

    if df.empty:
        st.success("✅ No slow or dead sizes detected")
        return

    st.warning("⚠️ Discount action recommended")

    st.dataframe(
        df.rename(columns={
            "brand": "Brand",
            "model": "Model",
            "color": "Color",
            "size": "Size",
            "current_stock": "Stock",
            "sold_30": "Sold (30d)",
            "sold_60": "Sold (60d)"
        })[
            [
                "Brand", "Model", "Color", "Size",
                "Stock", "Sold (30d)", "Sold (60d)",
                "Status", "Suggested Discount"
            ]
        ],
        hide_index=True,
        use_container_width=True
    )

# ----------------------------
# STOCK ALERTS
# ----------------------------
def stock_alerts():
    st.subheader("🚨 Low Stock Alerts")

    conn = get_db()
    df = pd.read_sql("SELECT * FROM products", conn)
    conn.close()

    df["stock"] = df["stock"].apply(
        lambda x: int.from_bytes(x, "little") if isinstance(x, bytes) else int(x)
    )

    alerts = df[df["stock"] <= df["reorder_level"]]

    if alerts.empty:
        st.success("All stock levels are healthy ✅")
    else:
        st.warning("Reorder required:")
        st.dataframe(
            alerts[["id", "brand", "model", "color", "stock", "reorder_level"]],
            hide_index=True,
            use_container_width=True,
        )

# ----------------------------
# ADMIN REPORTS + CHARTS
# ----------------------------
def admin_reports():
    st.subheader("📊 Admin Dashboard")

    # ----------------------------
    # DATE FILTERS
    # ----------------------------
    filter_option = st.radio(
        "Select Period",
        ["Today", "Yesterday", "This Week", "This Month", "Custom"],
        horizontal=True
    )

    today = pd.Timestamp.today().normalize()

    if filter_option == "Today":
        start_date = end_date = today

    elif filter_option == "Yesterday":
        start_date = end_date = today - pd.Timedelta(days=1)

    elif filter_option == "This Week":
        start_date = today - pd.Timedelta(days=today.weekday())
        end_date = today

    elif filter_option == "This Month":
        start_date = today.replace(day=1)
        end_date = today

    else:  # Custom
        col1, col2 = st.columns(2)
        with col1:
            start_date = pd.to_datetime(st.date_input("Start date", today))
        with col2:
            end_date = pd.to_datetime(st.date_input("End date", today))

    # ----------------------------
    # LOAD SALES DATA
    # ----------------------------
    conn = get_db()
    sales = pd.read_sql(
        """
        SELECT
            s.sale_id,
            s.product_id,
            p.brand,
            p.model,
            s.net_quantity AS quantity,
            s.net_revenue AS revenue,
            s.net_cost AS cost,
            s.sale_date,
            s.payment_method
        FROM net_sales s
        JOIN products p ON p.id = s.product_id
        """,
        conn
    )

    if "notes" not in sales.columns:
        sales["notes"] = ""
    conn.close()
    
    if sales.empty:
        st.info("No sales data available.")
        return

    sales["sale_date"] = pd.to_datetime(sales["sale_date"])
    sales["revenue"] = pd.to_numeric(sales["revenue"], errors="coerce").fillna(0)
    sales["cost"] = pd.to_numeric(sales["cost"], errors="coerce").fillna(0)

    # Apply date filter
    mask = (sales["sale_date"] >= start_date) & (sales["sale_date"] <= end_date)
    sales = sales.loc[mask]

    if sales.empty:
        st.warning("No sales found for selected period.")
        return

    # ----------------------------
    # KPIs
    # ----------------------------
    total_revenue = int(sales["revenue"].sum())
    total_cost = int(sales["cost"].sum())
    profit = total_revenue - total_cost

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue (KES)", total_revenue)
    c2.metric("Cost (KES)", total_cost)
    c3.metric("Profit (KES)", profit)
    c4.metric("Units Sold", int(sales["quantity"].sum()))

    st.divider()

    # ----------------------------
    # 📈 Revenue / Cost / Profit Trend
    # ----------------------------
    st.subheader("📈 Revenue, Cost & Profit")

    trend = sales.groupby("sale_date")[["revenue", "cost"]].sum()
    trend["profit"] = trend["revenue"] - trend["cost"]
    st.line_chart(trend)

    st.divider()

    # ----------------------------
    # 🔥 Top Selling Products
    # ----------------------------
    st.subheader("🔥 Top Selling Products")

    top_df = (
        sales.groupby(["brand", "model"])["quantity"]
        .sum()
        .reset_index()
        .sort_values(by="quantity", ascending=False)
    )
    top_df["product"] = top_df["brand"] + " " + top_df["model"]

    st.bar_chart(top_df.set_index("product")[["quantity"]])

    st.divider()

    # ----------------------------
    # 💳 Payment Breakdown
    # ----------------------------
    st.subheader("💳 Revenue by Payment Method")
    payment = sales.groupby("payment_method")["revenue"].sum()
    st.bar_chart(payment)

    st.divider()

    # ----------------------------
    # 🧾 Detailed Sales Table
    # ----------------------------
    st.subheader("🧾 Detailed Sales")
    st.dataframe(
        sales[
            ["product_id", "brand", "model",
            "quantity", "revenue", "payment_method", "notes", "sale_date"]
        ],
        hide_index=True,
        use_container_width=True,
    )

    st.divider()

    # ----------------------------
    # 📤 EXPORTS
    # ----------------------------
    st.subheader("📤 Export Sales Data")

    # ✅ CSV export (always available)
    csv = sales.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download CSV",
        data=csv,
        file_name="sales_report.csv",
        mime="text/csv",
    )

    # ⚠️ Excel export (only if engine exists)
    try:
        from io import BytesIO
        excel_buffer = BytesIO()
        sales.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)

        st.download_button(
            "⬇️ Download Excel",
            data=excel_buffer,
            file_name="sales_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception:
        st.info("ℹ️ Excel export not available on this system. Please use CSV.")

def admin_monthly_activity_summary():
    st.subheader("📅 Monthly Activity Summary")

    # Month selector
    selected_month = st.date_input(
        "Select Month",
        value=pd.Timestamp.today(),
        help="Pick any date within the month you want to review"
    )

    start_date = pd.to_datetime(selected_month).replace(day=1)
    end_date = start_date + pd.offsets.MonthEnd(1)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")


    conn = get_db()

    # ----------------------------
    # SALES SUMMARY
    # ----------------------------
    sales = pd.read_sql(
        """
        SELECT
            (revenue * (quantity - COALESCE(returned_quantity, 0)) / quantity) AS revenue,
            (cost * (quantity - COALESCE(returned_quantity, 0)) / quantity) AS cost,
            (quantity - COALESCE(returned_quantity, 0)) AS quantity,
            sale_date
        FROM sales
        WHERE sale_date BETWEEN ? AND ?
        AND return_status != 'FULL'
        """,
        conn,
        params=(start_str, end_str)
    )

    sales["revenue"] = pd.to_numeric(sales["revenue"], errors="coerce").fillna(0)
    sales["cost"] = pd.to_numeric(sales["cost"], errors="coerce").fillna(0)

    total_revenue = int(sales["revenue"].sum())
    total_cost = int(sales["cost"].sum())
    profit = total_revenue - total_cost
    sales_count = int(sales["quantity"].sum())

    # ----------------------------
    # RETURNS & EXCHANGES
    # ----------------------------
    re = pd.read_sql(
        """
        SELECT type, status, created_at
        FROM returns_exchanges
        WHERE date(created_at) BETWEEN ? AND ?
        """,
        conn,
        params=(start_str, end_str)
    )

    approved_returns = len(re[(re["type"] == "RETURN") & (re["status"] == "APPROVED")])
    rejected_returns = len(re[(re["type"] == "RETURN") & (re["status"] == "REJECTED")])
    exchanges = len(re[re["type"] == "EXCHANGE"])

    # ----------------------------
    # ACTIVITY LOG
    # ----------------------------
    activity = pd.read_sql(
        """
        SELECT event_type, message, created_at
        FROM activity_log
        WHERE date(created_at) BETWEEN ? AND ?
        ORDER BY created_at DESC
        """,
        conn,
        params=(start_str, end_str)
    )

    conn.close()

    # ----------------------------
    # METRICS
    # ----------------------------
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue (KES)", total_revenue)
    c2.metric("Profit (KES)", profit)
    c3.metric("Sales Count", sales_count)
    c4.metric("Exchanges", exchanges)

    c5, c6 = st.columns(2)
    c5.metric("Returns Approved", approved_returns)
    c6.metric("Returns Rejected", rejected_returns)

    st.divider()

    # ----------------------------
    # ACTIVITY TIMELINE
    # ----------------------------
    st.subheader("🕒 Activity Timeline")

    if activity.empty:
        st.info("No activity logged for this month.")
    else:
        for _, row in activity.iterrows():
            st.write(
                f"• **{row['event_type']}** — {row['message']} "
                f"({row['created_at']})"
            )

# ----------------------------
# ACTIVITY LOG (ADMIN VIEW)
# ----------------------------
def admin_activity_log():
    st.subheader("📋 System Activity Log")

    conn = get_db()
    logs = pd.read_sql(
        """
        SELECT event_type, reference_id, role, username, message, created_at
        FROM activity_log
        ORDER BY created_at DESC
        LIMIT 200
        """,
        conn
    )
    conn.close()

    if logs.empty:
        st.info("No activity logged yet.")
        return

    # Friendly labels
    logs.rename(
        columns={
            "event_type": "Event",
            "reference_id": "Ref ID",
            "role": "Role",
            "username": "User",
            "message": "Details",
            "created_at": "Timestamp"
        },
        inplace=True
    )

    st.dataframe(
        logs,
        use_container_width=True,
        hide_index=True
    )


# ----------------------------
# PRODUCT WORKFLOW
# ----------------------------
def add_or_update_product_size(cur, product_id, size, quantity):
    cur.execute(
        """
        SELECT 1 FROM product_sizes
        WHERE product_id = ? AND size = ?
        """,
        (product_id, size)
    )

    exists = cur.fetchone()

    if exists:
        cur.execute(
            """
            UPDATE product_sizes
            SET quantity = ?
            WHERE product_id = ? AND size = ?
            """,
            (quantity, product_id, size)
        )
    else:
        cur.execute(
            """
            INSERT INTO product_sizes (product_id, size, quantity)
            VALUES (?, ?, ?)
            """,
            (product_id, size, quantity)
        )

def manager_manage_sizes():
    st.subheader("📐 Add / Update Product Sizes")

    conn = get_db()
    products = pd.read_sql(
        "SELECT id, brand, model, color, category FROM products",
        conn
)
    
    conn.close()

    if products.empty:
        st.info("No products available.")
        return

    product_id = st.selectbox(
        "Select Product",
        products["id"],
        format_func=lambda x: (
            products[products["id"] == x][
                ["brand", "model", "color"]
            ]
            .iloc[0]
            .to_string()
        )
    )

    product_row = products[products["id"] == product_id].iloc[0]
    category = product_row["category"].lower()
    if category == "women":
        allowed_sizes = [str(s) for s in range(35, 42)]  # 35–41
    elif category == "men":
        allowed_sizes = [str(s) for s in range(40, 46)]  # 40–45
    else:
        allowed_sizes = [str(s) for s in range(35, 46)]  # fallback

    size = st.selectbox(
        f"Size (Allowed: {allowed_sizes[0]}–{allowed_sizes[-1]})",
        allowed_sizes,
        key=f"size_select_{product_id}"
    )

    quantity = st.number_input(
        "Quantity",
        min_value=0,
        step=1,
        key=f"manage_size_qty_{product_id}_{size}"
    )

    if st.button("💾 Save Size Stock"):
        conn = get_db()
        cur = conn.cursor()

        add_or_update_product_size(cur, product_id, size, quantity)

        sync_product_stock(cur, product_id)   # 👈 pass SAME cursor

        conn.commit()
        conn.close()

        st.success(f"✅ Size {size} set to {quantity}")

#reduce/adjust product stocks
def reduce_existing_product_stock(role):
    st.subheader("➖ Reduce Stock (Correction / Damage / Loss)")

    if role not in ["Admin", "Manager"]:
        st.error("Unauthorized")
        return

    conn = get_db()
    products = pd.read_sql(
        """
        SELECT id, brand, model, color, category
        FROM products
        WHERE is_active = 1
        ORDER BY brand, model
        """,
        conn
    )
    conn.close()

    if products.empty:
        st.info("No active products available.")
        return

    product_id = st.selectbox(
        "Select Product",
        products["id"],
        format_func=lambda x: (
            products[products["id"] == x][["brand", "model", "color"]]
            .iloc[0]
            .to_string()
        ),
        key=f"reduce_stock_product_{role}"
    )

    product = products[products["id"] == product_id].iloc[0]

    # Size logic
    if str(product["category"]).lower() == "women":
        allowed_sizes = [str(s) for s in range(35, 42)]
    else:
        allowed_sizes = [str(s) for s in range(40, 46)]

    size = st.selectbox(
        "Size",
        allowed_sizes,
        key=f"reduce_stock_size_{role}_{product_id}"
    )

    qty_to_reduce = st.number_input(
        "Quantity to Reduce",
        min_value=1,
        step=1,
        key=f"reduce_stock_qty_{role}_{product_id}_{size}"
    )

    reason = st.text_input(
        "Reason (required)",
        placeholder="e.g. damaged, lost, counting correction",
        key=f"reduce_stock_reason_{role}_{product_id}_{size}"
    )

    if st.button("➖ Confirm Reduce Stock", key=f"reduce_stock_submit_{role}_{product_id}_{size}"):

        if not reason.strip():
            st.error("❌ Reason is required for audit trail.")
            return

        conn = get_db()
        cur = conn.cursor()

        # 1️⃣ Check current size stock
        row = cur.execute(
            """
            SELECT quantity
            FROM product_sizes
            WHERE product_id = ? AND size = ?
            """,
            (int(product_id), str(size))
        ).fetchone()

        current_qty = int(row[0]) if row else 0

        # 2️⃣ Prevent negative stock
        if qty_to_reduce > current_qty:
            conn.close()
            st.error(f"❌ Cannot reduce {qty_to_reduce}. Current stock for size {size} is {current_qty}.")
            return

        # 3️⃣ Reduce stock
        new_qty = current_qty - int(qty_to_reduce)

        add_or_update_product_size(
            cur,
            int(product_id),
            str(size),
            new_qty
        )

        # 4️⃣ Sync total stock
        sync_product_stock(cur, int(product_id))

        # 5️⃣ Audit trail
        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "STOCK_REDUCED",
                int(product_id),
                role,
                st.session_state.username,
                f"Reduced size {size}, Qty {qty_to_reduce}. Reason: {reason}"
            )
        )

        conn.commit()
        conn.close()

        st.success("✅ Stock reduced successfully")
        st.rerun()

def admin_pending_buying_price():
    st.subheader("⚠️ Products Pending Buying Price")

    conn = get_db()
    df = pd.read_sql(
        "SELECT id, brand, model, color FROM products WHERE buying_price IS NULL",
        conn,
    )
    conn.close()

    if df.empty:
        st.success("No pending products 🎉")
        return

    pid = st.selectbox(
        "Select Product",
        df["id"],
        format_func=lambda x: df[df["id"] == x][["brand", "model", "color"]].iloc[0].to_string(),
    )

    buying_price = st.number_input(
        "Buying Price (KES)",
        min_value=0,
        key=f"admin_buying_price_{pid}"
    )


    if st.button("Save Buying Price"):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE products SET buying_price=? WHERE id=?",
            (buying_price, pid),
        )
        conn.commit()
        conn.close()
        st.success("✅ Buying price saved")

# ----------------------------
# STOCK MANAGEMENT (Admin & Manager)
#Update Restocked Products
def restock_existing_product(role):
    st.subheader("🔄 Restock Existing Product")

    conn = get_db()
    products = pd.read_sql(
        """
        SELECT id, brand, model, color, category, buying_price
        FROM products
        WHERE is_active = 1
        ORDER BY brand, model
        """,
        conn
    )
    conn.close()

    if products.empty:
        st.info("No active products available.")
        return

    product_id = st.selectbox(
        "Select Product",
        products["id"],
        format_func=lambda x: (
            products[products["id"] == x][["brand", "model", "color"]]
            .iloc[0]
            .to_string()
        ),
        key=f"restock_product_{role}"
    )

    product = products[products["id"] == product_id].iloc[0]

    # Size logic
    if product["category"].lower() == "women":
        allowed_sizes = [str(s) for s in range(35, 42)]
    else:
        allowed_sizes = [str(s) for s in range(40, 46)]

    size = st.selectbox(
        "Size",
        allowed_sizes,
        key=f"restock_size_{role}_{product_id}"
    )

    quantity = st.number_input(
        "Quantity to Add",
        min_value=1,
        step=1,
        key=f"restock_qty_{role}_{product_id}_{size}"
    )

    # Buying price logic
    if role == "Admin":
        unit_cost = st.number_input(
            "Buying Price per Unit (KES)",
            min_value=0,
            value=int(product["buying_price"] or 0),
            key=f"restock_cost_{role}_{product_id}"
        )
    else:
        unit_cost = product["buying_price"]
        st.caption(f"Admin will update buying price")

    if st.button("➕ Confirm Restock", key=f"restock_submit_{role}_{product_id}_{size}"):

        conn = get_db()
        cur = conn.cursor()

        # 1️⃣ Add size stock
        row = cur.execute(
            """
            SELECT quantity
            FROM product_sizes
            WHERE product_id = ? AND size = ?
            """,
            (product_id, size)
        ).fetchone()

        existing_qty = row[0] if row else 0

        add_or_update_product_size(
            cur,
            product_id,
            size,
            existing_qty + quantity
        )

        # 2️⃣ Update buying price (Admin only)
        if role == "Admin":
            cur.execute(
                "UPDATE products SET buying_price = ? WHERE id = ?",
                (unit_cost, product_id)
            )

        # 3️⃣ Sync total stock
        sync_product_stock(cur, product_id)

        # 4️⃣ Audit trail
        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "PRODUCT_RESTOCKED",
                product_id,
                role,
                st.session_state.username,
                f"Restocked size {size}, Qty {quantity}, Unit cost {unit_cost}"
            )
        )

        conn.commit()
        conn.close()

        st.success("✅ Restock completed successfully")
        st.rerun()

def add_product_and_sizes(role):
    st.subheader("➕ Add Product & Sizes")

    category = st.selectbox("Category", ["Women", "Men"])
    brand = st.text_input("Brand")
    model = st.text_input("Model")
    color = st.text_input("Color")

    selling_price = st.number_input(
    "Selling Price (KES)",
    min_value=0,
    key=f"{role}_new_product_selling_price"
    )

    if role == "Admin":
        buying_price = st.number_input(
            "Buying Price (KES)",
            min_value=0,
            key=f"{role}_new_product_buying_price"
        )
    else:
        buying_price = None
        st.info("ℹ️ Buying price will be added by Admin")

    # ----------------------------
    # SIZE INPUTS (REQUIRED)
    # ----------------------------
    st.markdown("### 📐 Sizes & Initial Stock")

    sizes = {}
    allowed_sizes = (
        range(35, 42) if category == "Women" else range(40, 46)
    )

    for size in allowed_sizes:
        qty = st.number_input(
            f"Size {size}",
            min_value=0,
            key=f"{role}_new_product_size_{size}"
        )
        if qty > 0:
            sizes[str(size)] = qty
    # ----------------------------
    # SAVE
    # ----------------------------
    if st.button("✅ Save Product"):
        if not brand or not model or not color:
            st.error("❌ All product fields are required.")
            return

        if not sizes:
            st.error("❌ You must add at least one size.")
            return

        conn = get_db()
        cur = conn.cursor()

        try:
            conn.execute("BEGIN")

            cur.execute(
                """
                INSERT INTO products
                (category, brand, model, color,
                 buying_price, selling_price, stock)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    category,
                    brand,
                    model,
                    color,
                    buying_price,
                    selling_price,
                )
            )

            product_id = cur.lastrowid

            for size, qty in sizes.items():
                cur.execute(
                    """
                    INSERT INTO product_sizes
                    (product_id, size, quantity)
                    VALUES (?, ?, ?)
                    """,
                    (product_id, size, qty)
                )

            sync_product_stock(cur, product_id)

            conn.commit()

            st.success("✅ Product created successfully")

        except Exception as e:
            conn.rollback()
            st.error(f"❌ Failed to save product: {e}")

        finally:
            conn.close()

#Pending Return Requests
def admin_handle_returns():
    st.subheader("🛂 Pending Return Requests")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            r.id AS request_id,
            r.sale_id,
            r.size,
            r.quantity AS return_qty,
            r.notes,
            r.initiated_by,
            p.id AS product_id,
            p.brand,
            p.model,
            p.color,
            s.quantity AS sold_qty,
            s.revenue,
            s.return_status,
            COALESCE(s.returned_quantity, 0) AS already_returned
        FROM returns_exchanges r
        JOIN sales s ON s.id = r.sale_id
        JOIN products p ON p.id = s.product_id
        WHERE r.type = 'RETURN'
        AND r.status = 'PENDING'
        AND s.return_status != 'FULL'
        ORDER BY r.created_at ASC
        """,
        conn
    )
    conn.close()
    if df.empty:
        st.success("No pending return requests 🎉")
        return

    # ----------------------------
    # Select request
    # ----------------------------
    request_id = st.selectbox(
        "Select Return Request",
        df["request_id"],
        format_func=lambda x: (
            df[df["request_id"] == x][
                ["brand", "model", "color", "size", "return_qty", "initiated_by"]
            ]
            .iloc[0]
            .to_string()
        )
    )

    row = df[df["request_id"] == request_id].iloc[0]

    st.info(
        f"""
        **Product:** {row['brand']} {row['model']} ({row['color']})  
        **Size:** {row['size']}  
        **Quantity to return:** {row['return_qty']}  
        **Requested by:** {row['initiated_by']}
        """
    )

    admin_note = st.text_area(
        "📝 Admin Notes",
        placeholder="Reason for approval or rejection"
    )

    col1, col2 = st.columns(2)

    # ----------------------------
    # APPROVE
    # ----------------------------
    with col1:
        if st.button("✅ Approve Return"):
            # Validate return quantity exists
            if row["return_qty"] is None or row["return_qty"] <= 0:
                st.error("❌ Invalid return quantity")
                return
                
            conn = get_db()
            cur = conn.cursor()
            
            # 1️⃣ Check current sale status
            # 1️⃣ Check current sale status
            cur.execute(
                """
                SELECT quantity, COALESCE(returned_quantity, 0), return_status
                FROM sales
                WHERE id = ?
                """,
                (int(row["sale_id"]),)
            )

            result = cur.fetchone()

            if not result:
                st.error(f"❌ Original sale record not found. Sale ID: {row['sale_id']}")
                conn.close()
                return

            # Force type conversion to integers
            sold_qty = int(result[0]) if result[0] is not None else 0
            already_returned = int(result[1]) if result[1] is not None else 0
            current_status = result[2] if result[2] is not None else 'NONE'

            # Account for other pending return requests on the same sale
            cur.execute("""
                SELECT COALESCE(SUM(quantity), 0)
                FROM returns_exchanges
                WHERE sale_id = ?
                  AND type = 'RETURN'
                  AND status = 'PENDING'
                  AND id != ?
            """, (int(row["sale_id"]), int(request_id)))
            pending_other = int(cur.fetchone()[0] or 0)

            st.write(
                f"🔍 Sale Check: Sold={sold_qty}, Already Returned={already_returned}, "
                f"Pending Other={pending_other}, Status={current_status}"
            )

            # 2️⃣ Prevent over-return
            if row["return_qty"] + already_returned + pending_other > sold_qty:
                st.error(
                    f"❌ Cannot approve return. "
                    f"Attempting to return {row['return_qty']}, "
                    f"but only {sold_qty - already_returned - pending_other} item(s) remain returnable."
                )
                conn.close()
                return

            # 3️⃣ Update sales table - THIS IS CRITICAL
            new_returned_qty = already_returned + row["return_qty"]
            new_status = 'FULL' if new_returned_qty >= sold_qty else 'PARTIAL'
            
            cur.execute(
                """
                UPDATE sales
                SET
                    returned_quantity = ?,
                    return_status = ?
                WHERE id = ?
                """,
                (new_returned_qty, new_status, int(row["sale_id"]))
            )
            
            # Verify the update worked
            rows_updated = cur.rowcount
            st.write(f"✅ Sales table updated: {rows_updated} row(s)")

            # 4️⃣ Restore stock to product_sizes
            cur.execute("""
            INSERT INTO product_sizes (product_id, size, quantity)
            VALUES (?, ?, 0)
            ON CONFLICT(product_id, size) DO NOTHING
            """, (int(row["product_id"]), str(row["size"])))

            cur.execute("""
            UPDATE product_sizes
            SET quantity = quantity + ?
            WHERE product_id = ? AND size = ?
            """, (
                int(row["return_qty"]),
                int(row["product_id"]),
                str(row["size"])
            ))

            # 5️⃣ Sync main product stock
            sync_product_stock(cur, row["product_id"])

            # 6️⃣ Mark return as approved
            cur.execute(
                """
                UPDATE returns_exchanges
                SET status = 'APPROVED',
                    approved_by = ?,
                    notes = COALESCE(notes, '') || ' | ADMIN: ' || ?
                WHERE id = ?
                """,
                (st.session_state.username, admin_note, int(request_id))
            )

            # 7️⃣ Activity log
            cur.execute(
                """
                INSERT INTO activity_log
                (event_type, reference_id, role, username, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "RETURN_APPROVED",
                    int(request_id),
                    "Admin",
                    st.session_state.username,
                    f"Approved return — Sale ID {row['sale_id']}, Size {row['size']}, Qty {row['return_qty']}. {admin_note}"
                )
            )
            
            conn.commit()
            conn.close()

            st.success("✅ Return approved successfully!")
            st.balloons()
            time.sleep(1)
            st.rerun()
    # ----------------------------
    # REJECT
    # ----------------------------
    with col2:
        if st.button("❌ Reject Return"):
            conn = get_db()
            cur = conn.cursor()

            cur.execute(
                """
                UPDATE returns_exchanges
                SET status = 'REJECTED',
                    notes = notes || ' | ADMIN: ' || ?
                WHERE id = ?
                """,
                (admin_note, request_id)
            )

            cur.execute(
                """
                INSERT INTO activity_log
                (event_type, reference_id, role, username, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "RETURN_REJECTED",
                    request_id,
                    "Admin",
                    st.session_state.username,
                    f"Rejected return — Size {row['size']}, Qty {row['return_qty']}. {admin_note}"
                )
            )

            conn.commit()
            conn.close()

            st.warning("❌ Return rejected")
            st.rerun()

def handle_admin_return_action(request_id, decision, admin_note):
    conn = get_db()
    cur = conn.cursor()

    # Update return request status
    cur.execute(
        """
        UPDATE returns_exchanges
        SET status = ?
        WHERE id = ?
        """,
        (decision, request_id)
    )

    # Log admin activity
    cur.execute(
        """
        INSERT INTO activity_log
        (event_type, reference_id, role, username, message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            f"RETURN_{decision}",
            request_id,
            "Admin",
            st.session_state.username,
            admin_note
        )
    )

    conn.commit()
    conn.close()

    st.success(f"Return request {decision.lower()} successfully")
    st.rerun()

#Returns and updates on sales history
def upgrade_sales_for_returns():
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("ALTER TABLE sales ADD COLUMN returned_quantity INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cur.execute("ALTER TABLE sales ADD COLUMN return_status TEXT DEFAULT 'NONE'")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


def admin_view_activity_log():
    st.subheader("🕒 System Activity Log")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT event_type, reference_id, role, username, message, created_at
        FROM activity_log
        ORDER BY created_at DESC
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.info("No activity recorded yet.")
        return

    # Ensure datetime
    df["created_at"] = pd.to_datetime(df["created_at"])

    # ----------------------------
    # FILTERS
    # ----------------------------
    with st.expander("🔍 Filters", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            start_date = st.date_input(
                "From date",
                df["created_at"].min().date()
            )

        with col2:
            end_date = st.date_input(
                "To date",
                df["created_at"].max().date()
            )

        with col3:
            users = ["All"] + sorted(df["username"].dropna().unique().tolist())
            selected_user = st.selectbox("User", users)

        event_types = ["All"] + sorted(df["event_type"].unique().tolist())
        selected_event = st.selectbox("Event Type", event_types)

    # ----------------------------
    # APPLY FILTERS
    # ----------------------------
    mask = (
        (df["created_at"].dt.date >= start_date) &
        (df["created_at"].dt.date <= end_date)
    )

    if selected_user != "All":
        mask &= df["username"] == selected_user

    if selected_event != "All":
        mask &= df["event_type"] == selected_event

    filtered = df.loc[mask]

    if filtered.empty:
        st.warning("No activity matches the selected filters.")
        return

    # ----------------------------
    # DISPLAY
    # ----------------------------
    st.dataframe(
        filtered,
        use_container_width=True,
        hide_index=True
    )
#Admin archive or restore products
def admin_archive_restore_product():
    st.subheader("🗄️ Archive / Restore Products")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT id, brand, model, color, is_active
        FROM products
        ORDER BY brand, model
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.info("No products available.")
        return

    pid = st.selectbox(
        "Select Product",
        df["id"],
        format_func=lambda x: (
            df[df["id"] == x][["brand", "model", "color"]]
            .iloc[0]
            .to_string()
        )
    )

    row = df[df["id"] == pid].iloc[0]
    is_active = int(row["is_active"])

    if is_active == 1:
        st.success("🟢 This product is ACTIVE")
        action = st.button("🗄️ Archive Product")
    else:
        st.warning("🗄️ This product is ARCHIVED")
        action = st.button("♻️ Restore Product")

    if action:
        conn = get_db()
        cur = conn.cursor()

        new_state = 0 if is_active == 1 else 1
        event = "PRODUCT_ARCHIVED" if new_state == 0 else "PRODUCT_RESTORED"

        cur.execute(
            "UPDATE products SET is_active=? WHERE id=?",
            (new_state, pid)
        )

        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event,
                pid,
                "Admin",
                st.session_state.username,
                f"{event.replace('_', ' ').title()}"
            )
        )

        conn.commit()
        conn.close()

        st.success("✅ Product status updated successfully")
        st.rerun()

#✅ returns_exchanges table ready
def manager_process_exchange():
    st.subheader("🔁 Process Exchange (Size-Aware, No Refund)")

    conn = get_db()

    sales = pd.read_sql(
        """
        SELECT
            s.sale_id,
            s.product_id,
            s.size AS sold_size,
            s.net_quantity AS quantity,
            p.brand,
            p.model,
            p.color,
            p.selling_price
        FROM net_sales s
        JOIN products p ON p.id = s.product_id
        ORDER BY s.sale_id DESC
        """,
        conn
    )

    if sales.empty:
        st.info("No sales available for exchange.")
        conn.close()
        return

    sale_id = st.selectbox(
        "Select Original Sale",
        sales["sale_id"],
        format_func=lambda x: (
            sales[sales["sale_id"] == x][
                ["brand", "model", "color", "sold_size", "quantity"]
            ].iloc[0].to_string()
        )
    )

    sale = sales[sales["sale_id"] == sale_id].iloc[0]

    product_id = int(sale["product_id"])
    old_size = str(sale["sold_size"])
    qty = int(sale["quantity"])
    price = int(sale["selling_price"])

    sizes_df = pd.read_sql(
        """
        SELECT size, quantity
        FROM product_sizes
        WHERE product_id = ?
        ORDER BY size
        """,
        conn,
        params=(product_id,)
    )

    new_size = st.selectbox(
        "Select Replacement Size",
        sizes_df["size"].astype(str).tolist()
    )

    notes = st.text_area("Exchange Notes")

    if st.button("🔁 Confirm Exchange"):

        if new_size == old_size:
            st.error("❌ Cannot exchange for the same size.")
            conn.close()
            return

        row = sizes_df[sizes_df["size"].astype(str) == new_size]

        if row.empty or int(row["quantity"].iloc[0]) < qty:
            st.error("❌ Not enough stock for selected size.")
            conn.close()
            return

        cur = conn.cursor()

        # 1️⃣ Restore original size
        cur.execute(
            """
            UPDATE product_sizes
            SET quantity = quantity + ?
            WHERE product_id = ? AND size = ?
            """,
            (qty, product_id, old_size)
        )

        # 2️⃣ Deduct new size
        cur.execute(
            """
            UPDATE product_sizes
            SET quantity = quantity - ?
            WHERE product_id = ? AND size = ?
            """,
            (qty, product_id, new_size)
        )

        # 3️⃣ Sync main stock
        sync_product_stock(cur, product_id)

        # 4️⃣ Log exchange
        cur.execute(
            """
            INSERT INTO returns_exchanges
            (sale_id, type, size, quantity, amount, notes, initiated_by, status)
            VALUES (?, 'EXCHANGE', ?, ?, 0, ?, ?, 'APPROVED')
            """,
            (
                sale_id,
                new_size,
                qty,
                notes,
                st.session_state.username
            )
        )

        # 5️⃣ Audit trail
        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "EXCHANGE_PROCESSED",
                sale_id,
                st.session_state.role,
                st.session_state.username,
                f"Exchanged size {old_size} → {new_size}, Qty {qty}. {notes}"
            )
        )

        conn.commit()
        conn.close()

        st.success("✅ Exchange completed successfully")

def manager_view_admin_updates():
    st.subheader("📢 Admin Updates")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT event_type, message, created_at
        FROM activity_log
        WHERE role = 'Admin'
          AND event_type IN (
              'RETURN_APPROVED',
              'RETURN_REJECTED',
              'EXCHANGE_REVIEWED'
          )
        ORDER BY created_at DESC
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.info("No updates from admin yet.")
        return

    df["created_at"] = pd.to_datetime(df["created_at"])

    for _, row in df.iterrows():
        if row["event_type"] == "RETURN_APPROVED":
            st.success(
                f"✅ Return approved\n\n"
                f"{row['message']}\n\n"
                f"🕒 {row['created_at']}"
            )

        elif row["event_type"] == "RETURN_REJECTED":
            st.error(
                f"❌ Return rejected\n\n"
                f"{row['message']}\n\n"
                f"🕒 {row['created_at']}"
            )

        else:
            st.info(
                f"ℹ️ Exchange reviewed\n\n"
                f"{row['message']}\n\n"
                f"🕒 {row['created_at']}"
            )

def manager_view_my_requests():
    st.subheader("📑 My Return & Exchange Requests")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            re.id AS request_id,
            re.type,
            re.status,
            re.notes,
            re.created_at,
            al.message AS admin_message,
            al.created_at AS reviewed_at
        FROM returns_exchanges re
        LEFT JOIN activity_log al
            ON al.reference_id = re.id
            AND al.event_type IN ('RETURN_APPROVED', 'RETURN_REJECTED')
        WHERE re.initiated_by = ?
        ORDER BY re.created_at DESC
        """,
        conn,
        params=(st.session_state.username,)
    )
    conn.close()

    if df.empty:
        st.info("No return or exchange requests yet.")
        return

    df = df.rename(columns={
        "type": "Request Type",
        "status": "Status",
        "notes": "Your Notes",
        "admin_message": "Admin Decision Notes",
        "created_at": "Requested At",
        "reviewed_at": "Reviewed At"
    })

    st.dataframe(
        df[
            [
                "Request Type",
                "Status",
                "Your Notes",
                "Admin Decision Notes",
                "Requested At",
                "Reviewed At",
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

# ----------------------------
# MANAGER: REQUEST RETURN (ADMIN APPROVAL)
# ----------------------------
def manager_request_return():
    st.subheader("↩️ Request Return (Admin Approval Required)")

    conn = get_db()
    sales = pd.read_sql(
        """
        SELECT
            s.sale_id,
            s.product_id,
            p.brand,
            p.model,
            p.color,
            s.size,
            s.net_quantity AS quantity,
            s.net_revenue AS revenue
        FROM net_sales s
        JOIN products p ON p.id = s.product_id
        ORDER BY s.sale_id DESC
        """,
        conn
    )

    conn.close()

    if sales.empty:
        st.info("No sales available for return.")
        return

    # ----------------------------
    # Select sale
    # ----------------------------
    sale_option = st.selectbox(
        "Select Sale to Return",
        sales["sale_id"],
        format_func=lambda x: (
            sales[sales["sale_id"] == x][
                ["brand", "model", "color", "size", "quantity", "revenue"]
            ]
            .iloc[0]
            .to_string()
        )
    )

    sale_row = sales[sales["sale_id"] == sale_option].iloc[0]

    return_size = str(sale_row["size"])
    max_qty = int(
        sale_row["quantity"] - sale_row.get("returned_quantity", 0)
    )
    # ----------------------------
    # Quantity to return
    # ----------------------------
    qty = st.number_input(
        "Quantity to return",
        min_value=1,
        max_value=max_qty,
        step=1
    )

    st.info(f"📏 Size: {return_size}")
    st.caption(f"Maximum returnable quantity: {max_qty}")

    notes = st.text_area(
        "Return Reason / Notes",
        placeholder="Reason for return, condition of item, etc."
    )

    # ----------------------------
    # Submit request
    # ----------------------------
    if st.button("📤 Submit Return Request"):
        conn = get_db()
        cur = conn.cursor()

        # Insert return request (SIZE-AWARE)
        cur.execute(
            """
            INSERT INTO returns_exchanges
            (sale_id, type, size, quantity, amount, notes, initiated_by, status)
            VALUES (?, 'RETURN', ?, ?, 0, ?, ?, 'PENDING')
            """,
            (
                sale_option,
                return_size,
                qty,
                notes,
                st.session_state.username
            )
        )

        # Log activity
        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "RETURN_REQUESTED",
                sale_option,
                st.session_state.role,      # Manager
                st.session_state.username,  # Who requested
                f"Size {return_size}, Qty {qty}. {notes}"
            )
        )

        conn.commit()
        conn.close()

        st.success("✅ Return request submitted for admin approval")

def manager_view_return_status():
    st.subheader("📄 My Return Requests Status")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT re.id AS request_id,
               re.sale_id,
               re.type,
               re.status,
               re.notes,
               re.created_at
        FROM returns_exchanges re
        WHERE re.initiated_by = ?
          AND re.type = 'RETURN'
        ORDER BY re.created_at DESC
        """,
        conn,
        params=(st.session_state.username,)
    )
    conn.close()

    if df.empty:
        st.info("You have not submitted any return requests yet.")
        return

    # Friendly labels
    df.rename(
        columns={
            "request_id": "Request ID",
            "sale_id": "Sale ID",
            "status": "Status",
            "notes": "Admin / Manager Notes",
            "created_at": "Submitted On"
        },
        inplace=True
    )

    st.dataframe(
        df[
            ["Request ID", "Sale ID", "Status", "Admin / Manager Notes", "Submitted On"]
        ],
        hide_index=True,
        use_container_width=True
    )

#Unified inventory 
def inventory_overview(role):
    st.subheader("📦 Inventory")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
        p.id AS product_id,
        p.brand,
        p.model,
        p.color,
        p.selling_price,
        p.buying_price,
        p.is_active,
        ps.size,
        ps.quantity
    FROM products p
    LEFT JOIN product_sizes ps ON ps.product_id = p.id
    ORDER BY p.brand, p.model, ps.size
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.info("No products in inventory.")
        return

    
    grouped = df.groupby(
        [
            "product_id",
            "brand",
            "model",
            "color",
            "selling_price",
            "buying_price",
            "is_active",
        ]
    )

    for (
        pid,
        brand,
        model,
        color,
        selling_price,
        buying_price,
        is_active,
    ), group in grouped:

        header = f"👟 {brand} {model} ({color})"
        with st.expander(header, expanded=False):
            status = "🟢 Active" if int(is_active) == 1 else "🗄️ Archived"
            st.caption(f"Status: {status}")
            # ---- Product summary ----
            col1, col2 = st.columns(2)

            new_brand = brand or ""
            new_model = model or ""
            new_selling = None
            new_buying = None

            with col1:
                st.write(f"**Brand:** {brand}")
                st.write(f"**Model:** {model}")
                st.write(f"**Color:** {color}")
                if role in ["Admin", "Manager"]:
                    new_brand = st.text_input(
                        "Update Brand",
                        value=brand or "",
                        key=f"brand_edit_{pid}"
                    )
                    new_model = st.text_input(
                        "Update Model",
                        value=model or "",
                        key=f"model_edit_{pid}"
                    )

            with col2:
                st.write(f"**Selling Price:** KES {selling_price}")
                if role == "Admin":
                    st.write(f"**Buying Price:** KES {buying_price or 'Pending'}")
                    new_selling = st.number_input(
                        "Update Selling Price (KES)",
                        min_value=0,
                        value=int(selling_price or 0),
                        key=f"sell_price_{pid}"
                    )
                    new_buying = st.number_input(
                        "Update Buying Price (KES)",
                        min_value=0,
                        value=int(buying_price or 0),
                        key=f"buy_price_{pid}"
                    )

            if role in ["Admin", "Manager"]:
                if st.button("Save Details", key=f"save_details_{pid}"):
                    conn = get_db()
                    cur = conn.cursor()
                    if role == "Admin" and new_selling is not None and new_buying is not None:
                        cur.execute(
                            "UPDATE products SET brand = ?, model = ?, selling_price = ?, buying_price = ? WHERE id = ?",
                            (new_brand.strip(), new_model.strip(), int(new_selling), int(new_buying), int(pid))
                        )
                    else:
                        cur.execute(
                            "UPDATE products SET brand = ?, model = ? WHERE id = ?",
                            (new_brand.strip(), new_model.strip(), int(pid))
                        )
                    conn.commit()
                    conn.close()
                    st.success("✅ Details updated")

            st.divider()

            # ---- Size breakdown ----
            sizes = group.dropna(subset=["size"])

            if sizes.empty:
                st.info("No sizes added for this product yet.")
                continue

            size_view = sizes[["size", "quantity"]].copy()
            size_view["quantity"] = size_view["quantity"].astype(int)

            st.markdown("**📏 Size Stock**")
            st.dataframe(
                size_view,
                hide_index=True,
                use_container_width=True
            )

#INVENTORY VALUATION (CLOSING STOCK @ COST)
def inventory_valuation_summary():
    st.subheader("💰 Inventory Valuation (At Cost)")

    conn = get_db()

    df = pd.read_sql(
        """
        SELECT
            p.id AS product_id,
            p.brand,
            p.model,
            p.color,
            p.buying_price,
            COALESCE(SUM(ps.quantity), 0) AS total_qty
        FROM products p
        LEFT JOIN product_sizes ps ON ps.product_id = p.id
        WHERE p.is_active = 1
        GROUP BY p.id
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.info("No inventory data available.")
        return

    df["buying_price"] = pd.to_numeric(df["buying_price"], errors="coerce")
    df["stock_value"] = df["buying_price"] * df["total_qty"]

    missing_cost = df[df["buying_price"].isna()]
    valid = df.dropna(subset=["buying_price"])

    total_value = int(valid["stock_value"].sum())
        # ----------------------------
    # STOCK IN TRANSIT VALUE
    # ----------------------------
    conn = get_db()
    transit = pd.read_sql(
        """
        SELECT SUM(quantity * unit_cost) AS transit_value
        FROM stock_in_transit
        """,
        conn
    )
    conn.close()

    transit_value = int(transit["transit_value"].iloc[0] or 0)

    st.divider()

    c3, c4 = st.columns(2)
    c3.metric("On-Hand Stock Value (KES)", total_value)
    c4.metric("Stock In Transit Value (KES)", transit_value)

    st.metric(
        "📊 Total Inventory Value (On-Hand + Transit)",
        total_value + transit_value
    )

    # ---- KPIs ----
    c1, c2 = st.columns(2)
    c1.metric("Total Units in Stock", int(valid["total_qty"].sum()))
    c2.metric("Total Stock Value (KES)", total_value)

    st.divider()

    # ---- Warnings ----
    if not missing_cost.empty:
        st.warning("⚠️ Some products have NO buying price — valuation incomplete")
        st.dataframe(
            missing_cost[["brand", "model", "color", "total_qty"]],
            hide_index=True,
            use_container_width=True
        )

    # ---- Detailed table ----
    st.markdown("### 📦 Inventory Value Breakdown")

    view = valid.copy()
    view["stock_value"] = view["stock_value"].astype(int)

    st.dataframe(
        view.rename(columns={
            "brand": "Brand",
            "model": "Model",
            "color": "Color",
            "buying_price": "Unit Cost",
            "total_qty": "Quantity",
            "stock_value": "Stock Value (KES)"
        })[
            ["Brand", "Model", "Color", "Quantity", "Unit Cost", "Stock Value (KES)"]
        ],
        hide_index=True,
        use_container_width=True
    )

#Add stock in transit
def add_stock_in_transit(role):
    st.subheader("🚚 Add Stock In Transit (Paid, Not Yet Received)")

    conn = get_db()
    products = pd.read_sql(
        "SELECT id, brand, model, color, category, buying_price FROM products WHERE is_active = 1",
        conn
    )
    conn.close()

    if products.empty:
        st.info("No active products available.")
        return

    product_id = st.selectbox( 
        "Select Product",
        products["id"],
        format_func=lambda x: (
            products[products["id"] == x][["brand", "model", "color"]]
            .iloc[0]
            .to_string()
        ),
        key=f"select_product_stock_transit_{role}"
    )

    product = products[products["id"] == product_id].iloc[0]

    # Size logic (same as inventory)
    if product["category"].lower() == "women":
        allowed_sizes = [str(s) for s in range(35, 42)]
    else:
        allowed_sizes = [str(s) for s in range(40, 46)]

    size = st.selectbox(
        "Size",
        allowed_sizes,
        key=f"stock_transit_size_{role}"
    )


    quantity = st.number_input(
        "Quantity",
        min_value=1,
        step=1,
        key=f"stock_transit_qty_{role}"
    )

    default_cost = product["buying_price"] or 0

    unit_cost = st.number_input(
        "Unit Cost (KES)",
        min_value=0,
        value=int(default_cost),
        key=f"stock_transit_unit_cost_{role}"

    )

    total_cost = quantity * unit_cost
    st.caption(f"💰 Total Value: KES {total_cost}")

    if st.button(
        "📦 Record Stock In Transit",
        key=f"stock_transit_submit_{role}"
    ):
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO stock_in_transit
            (product_id, size, quantity, unit_cost, total_cost, entered_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                size,
                quantity,
                unit_cost,
                total_cost,
                st.session_state.username
            )
        )

        # Audit trail
        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, role, username, message)
            VALUES (?, ?, ?, ?)
            """,
            (
                "STOCK_IN_TRANSIT_ADDED",
                role,
                st.session_state.username,
                f"Product ID {product_id}, Size {size}, Qty {quantity}, Value KES {total_cost}"
            )
        )

        conn.commit()
        conn.close()

        st.success("✅ Stock in transit recorded successfully") #-----

#View Stock In transit
def view_stock_in_transit():
    st.subheader("🚚 Stock In Transit (Paid, Not Yet Received)")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            p.brand,
            p.model,
            p.color,
            st.size,
            st.quantity,
            st.unit_cost,
            st.total_cost,
            st.entered_by,
            st.created_at
        FROM stock_in_transit st
        JOIN products p ON p.id = st.product_id
        ORDER BY st.created_at DESC
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.info("No stock currently in transit.")
        return

    df["created_at"] = pd.to_datetime(df["created_at"])

    st.dataframe(
        df.rename(columns={
            "brand": "Brand",
            "model": "Model",
            "color": "Color",
            "size": "Size",
            "quantity": "Qty",
            "unit_cost": "Unit Cost",
            "total_cost": "Total Value",
            "entered_by": "Entered By",
            "created_at": "Recorded At"
        }),
        hide_index=True,
        use_container_width=True
    ) #--------

#record opening inventory 
def record_opening_inventory():
    st.subheader("🧮 Record Opening Inventory (For COGS)")

    snapshot_date = st.date_input("Opening Inventory Date")
    total_value = st.number_input(
        "Opening Inventory Value (KES)",
        min_value=0.0,
        step=1.0
    )

    if st.button("💾 Save Opening Inventory"):
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO opening_inventory
            (snapshot_date, total_value, created_by)
            VALUES (?, ?, ?)
            """,
            (snapshot_date, total_value, st.session_state.username)
        )

        conn.commit()
        conn.close()

        st.success("✅ Opening inventory recorded")
#COGS Summary
def cogs_summary():
    st.subheader("📉 Cost of Goods Sold (COGS)")

    # ----------------------------
    # Period selector
    # ----------------------------
    period = st.radio(
        "Select Period",
        ["Today", "This Month", "Custom"],
        horizontal=True
    )

    today = pd.Timestamp.today().normalize()

    if period == "Today":
        start_date = end_date = today

    elif period == "This Month":
        start_date = today.replace(day=1)
        end_date = today

    else:
        col1, col2 = st.columns(2)
        with col1:
            start_date = pd.to_datetime(st.date_input("Start date", today))
        with col2:
            end_date = pd.to_datetime(st.date_input("End date", today))

    # ----------------------------
    # Load sales cost data
    # ----------------------------
    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            s.sale_date,
            s.net_cost AS cost,
            s.net_quantity AS quantity,
            p.brand,
            p.model,
            p.color
        FROM net_sales s
        JOIN products p ON p.id = s.product_id
        WHERE s.sale_date BETWEEN ? AND ?
        """,
        conn,
        params=(
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        )
    )

    conn.close()

    if df.empty:
        st.info("No sales recorded for selected period.")
        return

    df["cost"] = pd.to_numeric(df["cost"], errors="coerce").fillna(0)

    total_cogs = int(df["cost"].sum())
    total_units = int(df["quantity"].sum())

    # ----------------------------
    # KPIs
    # ----------------------------
    c1, c2 = st.columns(2)
    c1.metric("Total Units Sold", total_units)
    c2.metric("Total COGS (KES)", total_cogs)

    st.divider()

    # ----------------------------
    # Breakdown by product
    # ----------------------------
    breakdown = (
        df.groupby(["brand", "model", "color"])
        .agg(
            units_sold=("quantity", "sum"),
            cogs=("cost", "sum")
        )
        .reset_index()
    )

    breakdown["cogs"] = breakdown["cogs"].astype(int)

    st.markdown("### 📦 COGS Breakdown by Product")

    st.dataframe(
        breakdown.rename(columns={
            "brand": "Brand",
            "model": "Model",
            "color": "Color",
            "units_sold": "Units Sold",
            "cogs": "COGS (KES)"
        }),
        hide_index=True,
        use_container_width=True
    )

#Admin record Operating Expenses
def record_operating_expense():
    st.subheader("🧾 Record Operating Expense")

    expense_date = st.date_input("Expense Date")
    category = st.selectbox(
        "Expense Category",
        [
            "Rent",
            "Salaries",
            "Transport",
            "Utilities",
            "Marketing",
            "Internet",
            "Maintenance",
            "Miscellaneous"
        ]
    )

    description = st.text_input("Description (optional)")
    amount = st.number_input("Amount (KES)", min_value=0.0, step=1.0)

    if st.button("💾 Save Expense"):
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO operating_expenses
            (expense_date, category, description, amount, created_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                expense_date,
                category,
                description,
                amount,
                st.session_state.username
            )
        )

        conn.commit()
        conn.close()

        st.success("✅ Operating expense recorded")

#Operating Expenses Entry
def operating_expenses_entry():
    st.subheader("➕ Record Operating Expense")

    expense_date = st.date_input(
        "Expense Date",
        pd.Timestamp.today()
    )

    category = st.selectbox(
        "Expense Category",
        [
            "Rent",
            "Salaries & Wages",
            "Transport & Fuel",
            "Utilities",
            "Marketing",
            "Repairs & Maintenance",
            "Supplies",
            "Other"
        ]
    )

    description = st.text_input(
        "Description (optional)",
        placeholder="e.g. January shop rent, fuel for deliveries"
    )

    amount = st.number_input(
        "Amount (KES)",
        min_value=0,
        step=100
    )

    if st.button("💾 Save Expense"):
        if amount <= 0:
            st.error("❌ Expense amount must be greater than 0.")
            return

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO operating_expenses
            (expense_date, category, description, amount)
            VALUES (?, ?, ?, ?)
            """,
            (
                expense_date.strftime("%Y-%m-%d"),
                category,
                description,
                int(amount)
            )
        )

        conn.commit()
        conn.close()

        st.success("✅ Operating expenses recorded successfully")

# Home Expenses (Manager/Admin)
def home_expenses_entry():
    st.subheader("🏠 Home Expenses")

    st.markdown("### Step 1: Select Expense Date")
    expense_date = st.date_input("Expense Date", pd.Timestamp.today())
    st.caption(f"📅 Selected date: {expense_date.strftime('%Y-%m-%d')}")

    st.markdown("### Step 2: Expense Details")
    category = st.selectbox(
        "Expense Category",
        [
            "Rent",
            "Electricity (Power)",
            "Water",
            "Internet",
            "Garbage Collection",
            "Food & Groceries",
            "Transport / Fuel",
            "School Fees",
            "Medical / Health",
            "Household Supplies",
            "Clothing",
            "Personal Care",
            "Entertainment",
            "Insurance",
            "Loan Repayment",
            "Savings / Investments",
            "Repairs & Maintenance",
            "Gifts / Donations",
            "Childcare",
            "Mobile Airtime",
            "Other"
        ]
    )
    description = st.text_area(
        "Additional Notes (optional)",
        placeholder="Add more details if needed..."
    )
    amount = st.number_input("Amount (KES)", min_value=0, step=100)

    st.markdown("### Step 3: Review & Submit")
    st.markdown("**Expense Summary:**")
    st.write(f"Date: {expense_date.strftime('%Y-%m-%d')}")
    st.write(f"Category: {category}")
    st.write(f"Description: {description or category}")
    st.write(f"Amount: KES {int(amount)}")

    if st.button("✅ Submit Home Expense"):
        if amount <= 0:
            st.error("❌ Amount must be greater than 0.")
            return
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO home_expenses
            (expense_date, category, description, amount, created_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                expense_date.strftime("%Y-%m-%d"),
                category,
                description or category,
                int(amount),
                st.session_state.username
            )
        )
        conn.commit()
        conn.close()
        st.success("✅ Home expense recorded")

def home_expenses_summary(start_date=None, end_date=None):
    st.subheader("🏠 Home Expenses Summary")
    conn = get_db()
    cur = conn.cursor()
    if not start_date or not end_date:
        end_date = pd.Timestamp.today()
        start_date = end_date - pd.Timedelta(days=30)
    cur.execute("""
        SELECT expense_date, category, description, amount
        FROM home_expenses
        WHERE expense_date BETWEEN ? AND ?
        ORDER BY expense_date DESC
    """, (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))
    rows = cur.fetchall()
    if not rows:
        st.info("No home expenses recorded yet.")
        conn.close()
        return
    df = pd.DataFrame(rows, columns=["expense_date", "category", "description", "amount"])
    total = int(df["amount"].sum())
    st.metric("Total Home Expenses (KES)", total)
    st.dataframe(df, hide_index=True, use_container_width=True)
    breakdown = (
        df.groupby("category")["amount"]
        .sum()
        .reset_index()
        .sort_values(by="amount", ascending=False)
    )
    st.markdown("### 📂 Home Expenses by Category")
    st.dataframe(
        breakdown.rename(columns={"category": "Category", "amount": "Amount (KES)"}),
        hide_index=True,
        use_container_width=True
    )
    conn.close()

def home_expenses_monthly_report():
    st.subheader("🏠 Home Expenses Monthly Report")
    conn = get_db()
    cur = conn.cursor()
    month = st.date_input("Select Month", pd.Timestamp.today(), key="home_expenses_month")
    month_str = month.strftime("%Y-%m")
    cur.execute("""
        SELECT SUM(amount)
        FROM home_expenses
        WHERE strftime('%Y-%m', expense_date) = ?
    """, (month_str,))
    total = cur.fetchone()[0] or 0
    st.metric("Total Home Expenses (KES)", int(total))
    cur.execute("""
        SELECT expense_date, category, description, amount
        FROM home_expenses
        WHERE strftime('%Y-%m', expense_date) = ?
        ORDER BY expense_date DESC
    """, (month_str,))
    rows = cur.fetchall()
    if rows:
        df = pd.DataFrame(rows, columns=["expense_date", "category", "description", "amount"])
        st.dataframe(df, hide_index=True, use_container_width=True)
        breakdown = (
            df.groupby("category")["amount"]
            .sum()
            .reset_index()
            .sort_values(by="amount", ascending=False)
        )
        st.markdown("### 📂 Home Expenses by Category (Monthly)")
        st.dataframe(
            breakdown.rename(columns={"category": "Category", "amount": "Amount (KES)"}),
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No home expenses recorded for this month.")
    conn.close()

#Operating expenses summary totals and breakdown
def operating_expenses_summary(start_date=None, end_date=None):
    st.subheader("📉 Operating Expenses Summary")

    conn = get_db()

    if start_date and end_date:
        df = pd.read_sql(
            """
            SELECT category, amount
            FROM operating_expenses
            WHERE expense_date BETWEEN ? AND ?
            """,
            conn,
            params=(start_date, end_date)
        )
    else:
        df = pd.read_sql(
            """
            SELECT category, amount
            FROM operating_expenses
            """,
            conn
        )

    conn.close()

    if df.empty:
        st.info("No operating expenses recorded yet.")
        return

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    total_expenses = int(df["amount"].sum())

    st.metric("Total Operating Expenses (KES)", total_expenses)

    st.divider()

    by_category = (
        df.groupby("category")["amount"]
        .sum()
        .reset_index()
        .sort_values(by="amount", ascending=False)
    )

    st.markdown("### 📂 Expenses by Category")

    st.dataframe(
        by_category.rename(columns={
            "category": "Category",
            "amount": "Amount (KES)"
        }),
        hide_index=True,
        use_container_width=True
    )

    st.bar_chart(
        by_category.set_index("category")["amount"]
    )
#Detailed operating expenses view - for audit
def operating_expenses_detailed():
    st.subheader("📋 Operating Expenses — Detailed View")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            expense_date,
            category,
            description,
            amount,
            created_at
        FROM operating_expenses
        ORDER BY expense_date DESC
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.info("No operating expenses available.")
        return

    df["amount"] = df["amount"].astype(int)

    st.dataframe(
        df.rename(columns={
            "expense_date": "Date",
            "category": "Category",
            "description": "Description",
            "amount": "Amount (KES)",
            "created_at": "Recorded At"
        }),
        hide_index=True,
        use_container_width=True
    )
#P&L Summary
def profit_and_loss_statement():
    st.subheader("📑 Profit & Loss Statement")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("P&L Start Date", key="pl_start")
    with col2:
        end_date = st.date_input("P&L End Date", key="pl_end")

    conn = get_db()

    # ----------------------------
    # REVENUE (NET OF RETURNS)
    # ----------------------------
    revenue = pd.read_sql(
        """
        SELECT SUM(net_revenue) AS total
        FROM net_sales
        WHERE sale_date BETWEEN ? AND ?
        """,
        conn,
        params=(start_date, end_date)
    )["total"].iloc[0] or 0

    # ----------------------------
    # COGS (TRANSACTIONAL — NET OF RETURNS)
    # ----------------------------
    cogs = pd.read_sql(
        """
        SELECT SUM(net_revenue) AS total
        FROM net_sales
        WHERE sale_date BETWEEN ? AND ?
        """,
        conn,
        params=(start_date, end_date)
    )["total"].iloc[0] or 0

    # ----------------------------
    # OPERATING EXPENSES
    # ----------------------------
    expenses = pd.read_sql(
        """
        SELECT SUM(amount) AS total
        FROM operating_expenses
        WHERE expense_date BETWEEN ? AND ?
        """,
        conn,
        params=(start_date, end_date)
    )["total"].iloc[0] or 0

    conn.close()

    gross_profit = revenue - cogs
    net_profit = gross_profit - expenses

    # ---------------- DISPLAY ----------------
    st.markdown("### 🧮 P&L Summary")

    c1, c2, c3 = st.columns(3)
    c1.metric("Revenue (KES)", int(revenue))
    c2.metric("COGS (KES)", int(cogs))
    c3.metric("Gross Profit (KES)", int(gross_profit))

    st.divider()

    c4, c5 = st.columns(2)
    c4.metric("Operating Expenses (KES)", int(expenses))
    c5.metric("Net Profit (KES)", int(net_profit))


#Balance Sheet
def balance_sheet():
    st.subheader("📊 Balance Sheet")

    as_of = st.date_input(
        "As at Date",
        pd.Timestamp.today(),
        key="bs_date"
    )

    date_str = as_of.strftime("%Y-%m-%d")

    conn = get_db()

    # ----------------------------
    # ASSETS
    # ----------------------------

    # 1️⃣ Inventory on hand (at cost)
    inventory = pd.read_sql(
        """
        SELECT SUM(ps.quantity * p.buying_price) AS total
        FROM products p
        JOIN product_sizes ps ON ps.product_id = p.id
        WHERE p.is_active = 1
        """,
        conn
    )
    inventory_value = int(inventory.iloc[0]["total"] or 0)

    # 2️⃣ Stock in transit (already paid)
    transit = pd.read_sql(
        """
        SELECT SUM(total_cost) AS total
        FROM stock_in_transit
        WHERE date(created_at) <= ?
        """,
        conn,
        params=(date_str,)
    )
    transit_value = int(transit.iloc[0]["total"] or 0)

    # 3️⃣ Cash (derived)
    revenue = pd.read_sql(
        """
        SELECT SUM(net_revenue) AS total
        FROM net_sales
        WHERE sale_date <= ?
        """,
        conn,
        params=(date_str,)
    )["total"].iloc[0] or 0

    expenses = pd.read_sql(
        """
        SELECT SUM(amount) AS total
        FROM operating_expenses
        WHERE expense_date <= ?
        """,
        conn,
        params=(date_str,)
    )["total"].iloc[0] or 0

    cash_balance = int(revenue - expenses - transit_value)

    # ----------------------------
    # LIABILITIES (Phase 1)
    # ----------------------------
    liabilities = 0

    # ----------------------------
    # EQUITY
    # ----------------------------
    total_assets = inventory_value + transit_value + cash_balance
    equity = total_assets - liabilities

    conn.close()

    # ============================
    # DISPLAY
    # ============================
    st.markdown("### 🧾 Assets")

    a1, a2, a3 = st.columns(3)
    a1.metric("Cash (KES)", cash_balance)
    a2.metric("Inventory on Hand (KES)", inventory_value)
    a3.metric("Stock in Transit (KES)", transit_value)

    st.divider()

    st.markdown("### 🧾 Liabilities")
    st.metric("Total Liabilities (KES)", liabilities)

    st.divider()

    st.markdown("### 🧾 Equity")
    st.metric("Owner’s Equity (KES)", equity)

    st.divider()

    # ----------------------------
    # ACCOUNTING CHECK
    # ----------------------------
    st.success(
        f"✅ Assets (KES {total_assets}) = "
        f"Liabilities (KES {liabilities}) + "
        f"Equity (KES {equity})"
    )

    # Optional table
    with st.expander("📋 Balance Sheet Table View", expanded=False):
        bs = pd.DataFrame({
            "Category": [
                "Cash",
                "Inventory (On Hand)",
                "Inventory (In Transit)",
                "Total Assets",
                "Total Liabilities",
                "Owner's Equity"
            ],
            "Amount (KES)": [
                cash_balance,
                inventory_value,
                transit_value,
                total_assets,
                liabilities,
                equity
            ]
        })

        st.dataframe(bs, hide_index=True, use_container_width=True)
    if st.button("⬇️ Export Balance Sheet as PDF"):
        pdf_path = export_balance_sheet_pdf(
            as_of,
            cash_balance,
            inventory_value,
            transit_value,
            liabilities,
            equity
        )

        with open(pdf_path, "rb") as f:
            st.download_button(
                "📄 Download Balance Sheet (PDF)",
                f,
                file_name="Balance_Sheet.pdf",
                mime="application/pdf"
            )


def export_balance_sheet_pdf(as_of, cash, inventory, transit, liabilities, equity):
    file_path = "/mnt/data/Balance_Sheet.pdf"

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    elements = []

    # ----------------------------
    # TITLE
    # ----------------------------
    elements.append(Paragraph("<b>Shoes Nexus</b>", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(
        Paragraph(
            f"<b>Balance Sheet</b><br/>As at {as_of.strftime('%d %B %Y')}",
            styles["Heading2"]
        )
    )
    elements.append(Spacer(1, 20))

    # ----------------------------
    # ASSETS
    # ----------------------------
    elements.append(Paragraph("<b>ASSETS</b>", styles["Heading3"]))

    assets_table = [
        ["Cash", f"KES {cash:,}"],
        ["Inventory (On Hand)", f"KES {inventory:,}"],
        ["Inventory (In Transit)", f"KES {transit:,}"],
        ["<b>Total Assets</b>", f"<b>KES {cash + inventory + transit:,}</b>"]
    ]

    table = Table(assets_table, colWidths=[260, 200])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT")
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    # ----------------------------
    # LIABILITIES
    # ----------------------------
    elements.append(Paragraph("<b>LIABILITIES</b>", styles["Heading3"]))

    liabilities_table = [
        ["Total Liabilities", f"KES {liabilities:,}"]
    ]

    table = Table(liabilities_table, colWidths=[260, 200])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT")
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    # ----------------------------
    # EQUITY
    # ----------------------------
    elements.append(Paragraph("<b>EQUITY</b>", styles["Heading3"]))

    equity_table = [
        ["Owner’s Equity", f"KES {equity:,}"]
    ]

    table = Table(equity_table, colWidths=[260, 200])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT")
    ]))
    elements.append(table)
    elements.append(Spacer(1, 30))

    # ----------------------------
    # ACCOUNTING CHECK
    # ----------------------------
    elements.append(
        Paragraph(
            f"✔ Assets = Liabilities + Equity<br/>"
            f"KES {cash + inventory + transit:,} = "
            f"KES {liabilities:,} + KES {equity:,}",
            styles["Normal"]
        )
    )

    doc.build(elements)

    return file_path


# ----------------------------
# ROLE SCREENS
# ----------------------------
def cashier_home():
    st.title("🧾 Cashier")
    pos_screen(False)
    inventory_overview("Cashier")
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

def manager_home():
    st.title("📦 Manager")
    pos_screen(True)
    inventory_overview("Manager")
    st.divider()
    with st.expander ("🚨 Alerts and Stock Health", expanded=False):
        stock_alerts()
        zero_size_stock_alerts("Manager")
        size_stock_alerts("Manager")
        most_sold_sizes_per_product()
        most_sold_sizes_by_gender()
        dead_sizes_alerts()
        discount_suggestions()
        slow_sizes_alerts()
    st.divider()
    with st.expander("🔁 Returns and Exchanges", expanded=False):
        manager_process_exchange()
        manager_request_return()
        manager_view_return_status()
        manager_view_my_requests()
    st.divider()
    with st.expander("🛠️ Product and Size Management", expanded=False):
        add_product_and_sizes("Manager")
        restock_existing_product("Manager")
        reduce_existing_product_stock("Manager")
        add_stock_in_transit("Manager")
        view_stock_in_transit()

    with st.expander("📢 Admin Updates", expanded=False):
        manager_view_admin_updates()
    st.divider()
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

def admin_home():
    st.title("📊 Admin Dashboard")

    # 1️⃣ POS
    pos_screen(True)

    # 2️⃣ Inventory
    inventory_overview("Admin")
    st.divider()

    # 3️⃣ Alerts
    with st.expander("🚨 Alerts and Stock Health", expanded=False):
        stock_alerts()
        zero_size_stock_alerts("Admin")
        size_stock_alerts("Admin")
        slow_sizes_alerts()
        dead_sizes_alerts()
        discount_suggestions()
        inventory_valuation_summary()
        view_stock_in_transit()
        add_stock_in_transit("Admin")

    # 4️⃣ Sales Analytics
    with st.expander("📊 Sales and Size Analytics", expanded=False):
        admin_reports()
        most_sold_sizes_per_product()
        most_sold_sizes_by_gender()

    # 5️⃣ COGS (ONLY PLACE FOR OPENING INVENTORY)
    with st.expander("💼 Financials — COGS", expanded=False):
        record_opening_inventory()
        cogs_summary()

    # 6️⃣ Returns
    with st.expander("🔁 Returns and Exchanges", expanded=False):
        admin_handle_returns()
        admin_monthly_activity_summary()

    # 7️⃣ Audit Logs
    with st.expander("System Activity and Audit Logs", expanded=False):
        admin_view_activity_log()

    # 8️⃣ Product Management
    with st.expander("Product and Pricing Management", expanded=False):
        admin_pending_buying_price()
        restock_existing_product("Manager")
        reduce_existing_product_stock("Admin")
        admin_archive_restore_product()

    # 9️⃣ P&L (NO OPENING INVENTORY HERE)
    with st.expander("💼 Financials (P&L)", expanded=False):
        record_operating_expense()
        operating_expenses_summary()
        profit_and_loss_statement()
        balance_sheet()
    st.divider()
    with st.expander("🏠 Home Expenses", expanded=False):
        home_expenses_entry()
        home_expenses_summary()
        st.divider()
        home_expenses_monthly_report()

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()



# ----------------------------
# MAIN ROUTER
# ----------------------------
def main():
    st.set_page_config(page_title="Shoes Nexus", layout="centered")

    # ----------------------------
    # SESSION + DB INIT
    # ----------------------------
    init_session()
    ensure_activity_log()
    ensure_sales_source_column()
    ensure_product_public_fields()
    ensure_net_sales_view()
    ensure_operating_expenses_table()
    ensure_home_expenses_table()
    ensure_stock_in_transit_table()
    ensure_opening_inventory_table()
    upgrade_stock_in_transit_table()
    upgrade_sales_for_returns()

    # ----------------------------
    # SIDEBAR CSS (STYLE ONLY)
    # ----------------------------
    st.markdown("""
        <style>
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #2c3e50 0%, #34495e 100%);
        }

        [data-testid="stSidebar"] * {
            color: white !important;
        }

        .user-info {
            background: rgba(255,255,255,0.1);
            padding: 1rem;
            border-radius: 10px;
            margin-bottom: 1.5rem;
            text-align: center;
        }

        .user-name {
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 0.3rem;
        }

        .user-role {
            background: #3498db;
            padding: 0.3rem 0.8rem;
            border-radius: 15px;
            font-size: 0.85rem;
            display: inline-block;
        }

        .stButton > button {
            width: 100%;
            text-align: left;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            margin-bottom: 0.5rem;
            transition: all 0.3s ease;
        }

        .stButton > button:hover {
            background: rgba(255,255,255,0.2);
            transform: translateX(5px);
        }
        </style>
    """, unsafe_allow_html=True)

    # ============================================
    # CHECK IF LOGGED IN
    # ============================================
    if st.session_state.logged_in:
        auto_logout()

        # ============================================
        # SIDEBAR (ONLY ONE PLACE)
        # ============================================
        with st.sidebar:
            st.markdown(f"""
                <div class="user-info">
                    <div class="user-name">👤 {st.session_state.username}</div>
                    <div class="user-role">{st.session_state.role}</div>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("### 🧭 Navigation")

            if st.session_state.role == "Admin":
                if st.button("📊 Dashboard"):
                    st.switch_page("pages/dashboard.py")

                if st.button("👥 Manage Users"):
                    st.switch_page("pages/register_user.py")

                if st.button("📦 Initial Stock Setup"):
                    st.switch_page("pages/initial_stock_setup.py")

                if st.button("📅 Backdate Sales"):
                    st.switch_page("pages/backdate_sales.py")

                if st.button("💸 Backdate Expenses"):
                    st.switch_page("pages/backdate_expenses.py")

                if st.button("📦 Backdate Stock"):
                    st.switch_page("pages/backdate_stock_additions.py")

                if st.button("🔁 Returns & Exchanges"):
                    st.switch_page("pages/returns.py")

                if st.button("📈 Monthly Report"):
                    st.switch_page("pages/monthly_report.py")

            elif st.session_state.role == "Manager":
                if st.button("📊 Dashboard"):
                    st.switch_page("pages/dashboard.py")

                if st.button("📅 Backdate Sales"):
                    st.switch_page("pages/backdate_sales.py")

                if st.button("💸 Backdate Expenses"):
                    st.switch_page("pages/backdate_expenses.py")

                if st.button("📦 Backdate Stock"):
                    st.switch_page("pages/backdate_stock_additions.py")

                if st.button("🔁 Returns & Exchanges"):
                    st.switch_page("pages/returns.py")

            elif st.session_state.role == "Cashier":
                if st.button("🛒 POS System"):
                    st.switch_page("pages/pos.py")

                if st.button("🔁 Request Return"):
                    st.switch_page("pages/returns.py")

            st.markdown("---")

            if st.button("🚪 Logout"):
                st.session_state.clear()
                st.rerun()

        # ============================================
        # MAIN CONTENT AREA
        # ============================================
        if st.session_state.role == "Cashier":
            cashier_home()
        elif st.session_state.role == "Manager":
            manager_home()
        elif st.session_state.role == "Admin":
            admin_home()
        else:
            st.error("Unknown role")

    else:
        login_screen()


main()
