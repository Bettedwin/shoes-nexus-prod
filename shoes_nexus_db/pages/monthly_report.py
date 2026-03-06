from db_config import DB_PATH
import sqlite3
import io
import calendar
import pandas as pd
import streamlit as st
from theme_admin import apply_admin_theme

st.set_page_config(page_title="Monthly Report", layout="wide")
apply_admin_theme(
    "Monthly Report",
    "Monthly performance with drill-down sections for fast review.",
)


def safe_query(conn, query, params=(), columns=None):
    try:
        return pd.read_sql(query, conn, params=params)
    except Exception:
        return pd.DataFrame(columns=columns or [])


def fmt_int(value):
    return f"{int(value or 0):,}"


def ensure_monthly_stock_takes_table(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS monthly_stock_takes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_key TEXT NOT NULL,
            checkpoint_type TEXT NOT NULL,
            due_date DATE NOT NULL,
            completed_at DATETIME,
            total_products INTEGER,
            total_units INTEGER,
            total_value REAL,
            completed_by TEXT,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(month_key, checkpoint_type)
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_monthly_stock_takes_month_due "
        "ON monthly_stock_takes(month_key, due_date)"
    )
    conn.commit()


def month_schedule_dates(month_key):
    year, month = [int(x) for x in str(month_key).split("-")]
    start_dt = pd.Timestamp(year=year, month=month, day=1)
    end_day = calendar.monthrange(year, month)[1]
    end_dt = pd.Timestamp(year=year, month=month, day=end_day)
    return {
        "OPENING": start_dt.strftime("%Y-%m-%d"),
        "AUDIT_1": (start_dt + pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
        "AUDIT_2": (start_dt + pd.Timedelta(days=14)).strftime("%Y-%m-%d"),
        "CLOSING": end_dt.strftime("%Y-%m-%d"),
    }


def ensure_month_schedule_rows(conn, month_key):
    schedule = month_schedule_dates(month_key)
    cur = conn.cursor()
    for checkpoint_type, due_date in schedule.items():
        cur.execute(
            """
            INSERT OR IGNORE INTO monthly_stock_takes
            (month_key, checkpoint_type, due_date)
            VALUES (?, ?, ?)
            """,
            (str(month_key), str(checkpoint_type), str(due_date)),
        )
    conn.commit()


def get_live_inventory_totals(conn):
    df = safe_query(
        conn,
        """
        SELECT
            COALESCE(p.id, 0) AS product_id,
            COALESCE(ps.quantity, 0) AS quantity,
            COALESCE(p.buying_price, 0) AS buying_price
        FROM products p
        LEFT JOIN product_sizes ps ON ps.product_id = p.id
        WHERE COALESCE(p.is_active, 0) = 1
          AND NOT (
              LOWER(TRIM(COALESCE(p.category, ''))) = 'external'
              AND LOWER(TRIM(COALESCE(p.brand, ''))) = 'brokered'
              AND LOWER(TRIM(COALESCE(p.model, ''))) = 'brokered sale'
          )
        """,
        columns=["product_id", "quantity", "buying_price"],
    )
    if df.empty:
        return {"total_products": 0, "total_units": 0, "total_value": 0.0}
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["buying_price"] = pd.to_numeric(df["buying_price"], errors="coerce").fillna(0)
    df = df[df["quantity"] > 0]
    if df.empty:
        return {"total_products": 0, "total_units": 0, "total_value": 0.0}
    total_products = int(df["product_id"].nunique())
    total_units = int(df["quantity"].sum())
    total_value = float((df["quantity"] * df["buying_price"]).sum())
    return {"total_products": total_products, "total_units": total_units, "total_value": total_value}


def build_monthly_pdf_bytes(
    month_label,
    summary_df,
    top_styles_df,
    sources_df,
    riders_df,
    locations_df,
    expenses_df,
    quality_df,
):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except Exception as e:
        raise RuntimeError(f"PDF dependency error: {e}")

    def make_table(df, col_widths=None, max_rows=20):
        if df is None or df.empty:
            return Paragraph("No data.", styles["Normal"])
        clipped = df.head(max_rows).copy()
        for col in clipped.columns:
            clipped[col] = clipped[col].astype(str)
        data = [list(clipped.columns)] + clipped.values.tolist()
        tbl = Table(data, colWidths=col_widths)
        tbl.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f2f7")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        return tbl

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=28, leftMargin=28, topMargin=28, bottomMargin=28)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>Shoes Nexus Monthly Report</b>", styles["Title"]))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(f"Period: {month_label}", styles["Heading3"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>Executive Summary</b>", styles["Heading3"]))
    elements.append(make_table(summary_df, max_rows=20))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>Top Sold Styles</b>", styles["Heading3"]))
    elements.append(make_table(top_styles_df, max_rows=15))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>Customer Sources</b>", styles["Heading3"]))
    elements.append(make_table(sources_df, max_rows=15))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>Delivery by Rider/Courier</b>", styles["Heading3"]))
    elements.append(make_table(riders_df, max_rows=15))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("<b>Delivery by Location</b>", styles["Heading3"]))
    elements.append(make_table(locations_df, max_rows=15))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>Expenses by Category</b>", styles["Heading3"]))
    elements.append(make_table(expenses_df, max_rows=20))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>Data Quality</b>", styles["Heading3"]))
    elements.append(make_table(quality_df, max_rows=10))

    doc.build(elements)
    return buffer.getvalue()


conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")
today = pd.Timestamp.today()
month_names = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

years_df = safe_query(
    conn,
    """
    SELECT DISTINCT y FROM (
        SELECT strftime('%Y', sale_date) AS y FROM sales
        UNION
        SELECT strftime('%Y', expense_date) AS y FROM operating_expenses
    )
    WHERE y IS NOT NULL AND TRIM(y) != ''
    ORDER BY y
    """,
    columns=["y"],
)
years = []
for y in years_df.get("y", []):
    try:
        years.append(int(y))
    except Exception:
        pass
if not years:
    years = [int(today.year)]
if int(today.year) not in years:
    years.append(int(today.year))
years = sorted(set(years))

mode = st.radio(
    "Report Mode",
    ["Single Month", "Month Range", "Compare Months"],
    horizontal=True,
    key="monthly_report_mode",
)

def month_key(year_val, month_val):
    return f"{int(year_val):04d}-{int(month_val):02d}"

if mode == "Single Month":
    c1, c2 = st.columns(2)
    with c1:
        selected_month_name = st.selectbox(
            "Month",
            month_names,
            index=int(today.month) - 1,
            key="monthly_single_month_name",
        )
    with c2:
        selected_year = st.selectbox(
            "Year",
            years,
            index=years.index(int(today.year)),
            key="monthly_single_year",
        )
    month_str = month_key(selected_year, month_names.index(selected_month_name) + 1)
    period_label = pd.Timestamp(year=int(selected_year), month=month_names.index(selected_month_name) + 1, day=1).strftime("%B %Y")
    sales_period_clause = "strftime('%Y-%m', sale_date) = ?"
    sales_period_params = (month_str,)
    expense_period_clause = "strftime('%Y-%m', expense_date) = ?"
    expense_period_params = (month_str,)
    online_period_clause = "strftime('%Y-%m', created_at) = ?"
    online_period_params = (month_str,)
    report_month_str = month_str
elif mode == "Month Range":
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        start_month_name = st.selectbox("Start Month", month_names, index=int(today.month) - 1, key="monthly_range_start_month")
    with c2:
        start_year = st.selectbox("Start Year", years, index=years.index(int(today.year)), key="monthly_range_start_year")
    with c3:
        end_month_name = st.selectbox("End Month", month_names, index=int(today.month) - 1, key="monthly_range_end_month")
    with c4:
        end_year = st.selectbox("End Year", years, index=years.index(int(today.year)), key="monthly_range_end_year")

    start_key = month_key(start_year, month_names.index(start_month_name) + 1)
    end_key = month_key(end_year, month_names.index(end_month_name) + 1)
    if start_key > end_key:
        st.error("Start month must be before or equal to end month.")
        conn.close()
        st.stop()
    period_label = f"{start_key} to {end_key}"
    sales_period_clause = "strftime('%Y-%m', sale_date) BETWEEN ? AND ?"
    sales_period_params = (start_key, end_key)
    expense_period_clause = "strftime('%Y-%m', expense_date) BETWEEN ? AND ?"
    expense_period_params = (start_key, end_key)
    online_period_clause = "strftime('%Y-%m', created_at) BETWEEN ? AND ?"
    online_period_params = (start_key, end_key)
    report_month_str = end_key
else:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        month_a_name = st.selectbox("Month A", month_names, index=max(int(today.month) - 2, 0), key="monthly_cmp_a_month")
    with c2:
        year_a = st.selectbox("Year A", years, index=years.index(int(today.year)), key="monthly_cmp_a_year")
    with c3:
        month_b_name = st.selectbox("Month B", month_names, index=int(today.month) - 1, key="monthly_cmp_b_month")
    with c4:
        year_b = st.selectbox("Year B", years, index=years.index(int(today.year)), key="monthly_cmp_b_year")

    month_a_str = month_key(year_a, month_names.index(month_a_name) + 1)
    month_b_str = month_key(year_b, month_names.index(month_b_name) + 1)
    period_label = f"{month_a_str} vs {month_b_str}"
    sales_period_clause = "strftime('%Y-%m', sale_date) = ?"
    sales_period_params = (month_b_str,)
    expense_period_clause = "strftime('%Y-%m', expense_date) = ?"
    expense_period_params = (month_b_str,)
    online_period_clause = "strftime('%Y-%m', created_at) = ?"
    online_period_params = (month_b_str,)
    report_month_str = month_b_str

st.caption(f"Showing report for: {period_label}")

ensure_monthly_stock_takes_table(conn)
stock_take_month_key = report_month_str
ensure_month_schedule_rows(conn, stock_take_month_key)

stock_take_df = safe_query(
    conn,
    """
    SELECT
        checkpoint_type,
        due_date,
        completed_at,
        COALESCE(total_products, 0) AS total_products,
        COALESCE(total_units, 0) AS total_units,
        COALESCE(total_value, 0) AS total_value,
        COALESCE(completed_by, '') AS completed_by
    FROM monthly_stock_takes
    WHERE month_key = ?
    ORDER BY due_date ASC
    """,
    params=(stock_take_month_key,),
    columns=["checkpoint_type", "due_date", "completed_at", "total_products", "total_units", "total_value", "completed_by"],
)

st.subheader("Mandatory Stock Take Schedule")
st.caption(
    f"Required checkpoints for {stock_take_month_key}: OPENING (month start), AUDIT_1 (+7 days), AUDIT_2 (+14 days), CLOSING (month end)."
)

if stock_take_df.empty:
    st.warning("No stock take schedule found for this month.")
    mandatory_checkpoints_complete = False
else:
    stock_take_status = stock_take_df.copy()
    now_date = pd.Timestamp.today().strftime("%Y-%m-%d")
    stock_take_status["status"] = stock_take_status.apply(
        lambda r: (
            "COMPLETED"
            if pd.notna(r["completed_at"]) and str(r["completed_at"]).strip() != ""
            else ("OVERDUE" if str(r["due_date"]) < now_date else "PENDING")
        ),
        axis=1,
    )
    show_take = stock_take_status.rename(
        columns={
            "checkpoint_type": "Checkpoint",
            "due_date": "Due Date",
            "completed_at": "Completed At",
            "total_products": "Total Products",
            "total_units": "Total Units",
            "total_value": "Total Value (KES)",
            "completed_by": "Completed By",
            "status": "Status",
        }
    )
    show_take["Total Value (KES)"] = show_take["Total Value (KES)"].map(lambda x: int(float(x or 0)))
    st.dataframe(show_take, hide_index=True, use_container_width=True)

    pending_rows = stock_take_status[stock_take_status["status"] != "COMPLETED"]
    mandatory_checkpoints_complete = pending_rows.empty
    if not pending_rows.empty:
        overdue_rows = pending_rows[pending_rows["status"] == "OVERDUE"]
        if not overdue_rows.empty:
            st.error("Stock take enforcement: overdue checkpoints must be completed.")
        else:
            st.warning("Stock take enforcement: pending checkpoints remain.")
    st.info("Complete mandatory and ad-hoc stock takes from the Stock Take module.")
    if st.button("Open Stock Take", key="monthly_open_stock_take", use_container_width=True):
        st.switch_page("pages/stock_take.py")

prev_month = (pd.Timestamp(f"{report_month_str}-01").replace(day=1) - pd.Timedelta(days=1)).strftime("%Y-%m")
ns_sales_period_clause = sales_period_clause.replace("sale_date", "ns.sale_date")
s_sales_period_clause = sales_period_clause.replace("sale_date", "s.sale_date")

# Core financials
core = safe_query(
    conn,
    f"""
    SELECT
        COALESCE(SUM(net_revenue), 0) AS revenue,
        COALESCE(SUM(net_cost), 0) AS cost,
        COALESCE(SUM(net_quantity), 0) AS units
    FROM net_sales
    WHERE {sales_period_clause}
    """,
    params=sales_period_params,
    columns=["revenue", "cost", "units"],
)
prev_core = safe_query(
    conn,
    """
    SELECT
        COALESCE(SUM(net_revenue), 0) AS revenue
    FROM net_sales
    WHERE strftime('%Y-%m', sale_date) = ?
    """,
    params=(prev_month,),
    columns=["revenue"],
)
ads_legacy = safe_query(
    conn,
    f"""
    SELECT COALESCE(SUM(amount), 0) AS total
    FROM daily_expenses
    WHERE {expense_period_clause}
    """,
    params=expense_period_params,
    columns=["total"],
)
ads_marketing = safe_query(
    conn,
    f"""
    SELECT COALESCE(SUM(amount), 0) AS total
    FROM operating_expenses
    WHERE {expense_period_clause}
      AND LOWER(TRIM(COALESCE(category, ''))) IN (
          'marketing',
          'ads spend',
          'advertising',
          'ads',
          'digital marketing'
      )
    """,
    params=expense_period_params,
    columns=["total"],
)
operating = safe_query(
    conn,
    f"""
    SELECT COALESCE(SUM(amount), 0) AS total
    FROM operating_expenses
    WHERE {expense_period_clause}
    """,
    params=expense_period_params,
    columns=["total"],
)
ops_totals = safe_query(
    conn,
    f"""
    SELECT
        COALESCE(SUM(s.quantity), 0) AS total_products_sold,
        COALESCE(
            SUM(
                CASE
                    WHEN COALESCE(s.customer_count_unit, 0) > 0 THEN s.customer_count_unit
                    ELSE 0
                END
            ),
            0
        ) AS total_customers_served
    FROM sales s
    WHERE {s_sales_period_clause}
    """,
    params=sales_period_params,
    columns=["total_products_sold", "total_customers_served"],
)
returns_totals = safe_query(
    conn,
    f"""
    SELECT
        COALESCE(SUM(CASE WHEN re.type = 'RETURN' AND re.status = 'APPROVED' THEN re.quantity ELSE 0 END), 0) AS total_products_returned,
        COALESCE(SUM(CASE WHEN re.type = 'EXCHANGE' AND re.status = 'APPROVED' THEN re.quantity ELSE 0 END), 0) AS total_products_exchanged
    FROM returns_exchanges re
    JOIN sales s ON s.id = re.sale_id
    WHERE {s_sales_period_clause}
    """,
    params=sales_period_params,
    columns=["total_products_returned", "total_products_exchanged"],
)

revenue = int(core["revenue"].iloc[0] if not core.empty else 0)
cost = int(core["cost"].iloc[0] if not core.empty else 0)
units = int(core["units"].iloc[0] if not core.empty else 0)
gross_profit = int(revenue - cost)
ads_spend_marketing = float(ads_marketing["total"].iloc[0] if not ads_marketing.empty else 0)
ads_spend = int(ads_spend_marketing)
operating_exp = int(operating["total"].iloc[0] if not operating.empty else 0)
net_after_ops = int(gross_profit - operating_exp)
prev_revenue = int(prev_core["revenue"].iloc[0] if not prev_core.empty else 0)
revenue_delta = int(revenue - prev_revenue)
total_products_sold = int(ops_totals["total_products_sold"].iloc[0] if not ops_totals.empty else 0)
total_customers_served = int(ops_totals["total_customers_served"].iloc[0] if not ops_totals.empty else 0)
total_products_returned = int(returns_totals["total_products_returned"].iloc[0] if not returns_totals.empty else 0)
total_products_exchanged = int(returns_totals["total_products_exchanged"].iloc[0] if not returns_totals.empty else 0)

opening_take = stock_take_df[stock_take_df["checkpoint_type"] == "OPENING"] if not stock_take_df.empty else pd.DataFrame()
closing_take = stock_take_df[stock_take_df["checkpoint_type"] == "CLOSING"] if not stock_take_df.empty else pd.DataFrame()
opening_products = int(opening_take["total_products"].iloc[0]) if (not opening_take.empty and pd.notna(opening_take["completed_at"].iloc[0])) else 0
opening_value = int(float(opening_take["total_value"].iloc[0])) if (not opening_take.empty and pd.notna(opening_take["completed_at"].iloc[0])) else 0
closing_products = int(closing_take["total_products"].iloc[0]) if (not closing_take.empty and pd.notna(closing_take["completed_at"].iloc[0])) else 0
closing_value = int(float(closing_take["total_value"].iloc[0])) if (not closing_take.empty and pd.notna(closing_take["completed_at"].iloc[0])) else 0

if mode == "Compare Months":
    compare_core = safe_query(
        conn,
        """
        SELECT
            strftime('%Y-%m', sale_date) AS month_key,
            COALESCE(SUM(net_revenue), 0) AS revenue,
            COALESCE(SUM(net_cost), 0) AS cost,
            COALESCE(SUM(net_quantity), 0) AS units
        FROM net_sales
        WHERE strftime('%Y-%m', sale_date) IN (?, ?)
        GROUP BY strftime('%Y-%m', sale_date)
        ORDER BY month_key
        """,
        params=(month_a_str, month_b_str),
        columns=["month_key", "revenue", "cost", "units"],
    )
    compare_ops = safe_query(
        conn,
        """
        SELECT
            strftime('%Y-%m', expense_date) AS month_key,
            COALESCE(SUM(amount), 0) AS operating_expenses
        FROM operating_expenses
        WHERE strftime('%Y-%m', expense_date) IN (?, ?)
        GROUP BY strftime('%Y-%m', expense_date)
        ORDER BY month_key
        """,
        params=(month_a_str, month_b_str),
        columns=["month_key", "operating_expenses"],
    )
    cmp = compare_core.merge(compare_ops, on="month_key", how="left").fillna(0)
    if not cmp.empty:
        cmp["gross_profit"] = cmp["revenue"] - cmp["cost"]
        cmp["net_after_ops"] = cmp["gross_profit"] - cmp["operating_expenses"]
        st.subheader("Month Comparison")
        c_a = cmp[cmp["month_key"] == month_a_str]
        c_b = cmp[cmp["month_key"] == month_b_str]
        a_rev = int(c_a["revenue"].iloc[0]) if not c_a.empty else 0
        b_rev = int(c_b["revenue"].iloc[0]) if not c_b.empty else 0
        a_net = int(c_a["net_after_ops"].iloc[0]) if not c_a.empty else 0
        b_net = int(c_b["net_after_ops"].iloc[0]) if not c_b.empty else 0
        k1, k2, k3 = st.columns(3)
        k1.metric(f"Revenue {month_a_str}", fmt_int(a_rev))
        k2.metric(f"Revenue {month_b_str}", fmt_int(b_rev), delta=fmt_int(b_rev - a_rev))
        k3.metric(f"Net After OPEX {month_b_str}", fmt_int(b_net), delta=fmt_int(b_net - a_net))
        cmp_show = cmp.rename(
            columns={
                "month_key": "Month",
                "revenue": "Revenue (KES)",
                "cost": "COGS (KES)",
                "gross_profit": "Gross Profit (KES)",
                "operating_expenses": "Operating Expenses (KES)",
                "net_after_ops": "Net After OPEX (KES)",
                "units": "Units Sold",
            }
        )
        for col in ["Revenue (KES)", "COGS (KES)", "Gross Profit (KES)", "Operating Expenses (KES)", "Net After OPEX (KES)", "Units Sold"]:
            cmp_show[col] = cmp_show[col].map(lambda x: int(x))
        st.dataframe(cmp_show, hide_index=True, use_container_width=True)

# Most sold product
top_product = safe_query(
    conn,
    f"""
    SELECT
        COALESCE(p.brand, 'Unknown') || ' ' || COALESCE(p.model, '') AS product,
        COALESCE(SUM(ns.net_quantity), 0) AS units_sold,
        COALESCE(SUM(ns.net_revenue), 0) AS revenue
    FROM net_sales ns
    LEFT JOIN products p ON p.id = ns.product_id
    WHERE {ns_sales_period_clause}
      AND COALESCE(ns.notes, '') NOT LIKE '%Brokered Sale%'
    GROUP BY ns.product_id, p.brand, p.model
    ORDER BY units_sold DESC, revenue DESC
    LIMIT 1
    """,
    params=sales_period_params,
    columns=["product", "units_sold", "revenue"],
)
top_product_name = str(top_product["product"].iloc[0]) if not top_product.empty else "No product sales yet"
top_product_units = int(top_product["units_sold"].iloc[0]) if not top_product.empty else 0

top_variant = safe_query(
    conn,
    f"""
    SELECT
        COALESCE(p.brand, 'Unknown') || ' ' || COALESCE(p.model, '') AS product,
        COALESCE(p.color, 'N/A') AS color,
        COALESCE(ns.size, 'N/A') AS size,
        COALESCE(SUM(ns.net_quantity), 0) AS units_sold,
        COALESCE(SUM(ns.net_revenue), 0) AS revenue
    FROM net_sales ns
    LEFT JOIN products p ON p.id = ns.product_id
    WHERE {ns_sales_period_clause}
      AND COALESCE(ns.notes, '') NOT LIKE '%Brokered Sale%'
    GROUP BY ns.product_id, p.brand, p.model, p.color, ns.size
    ORDER BY units_sold DESC, revenue DESC
    LIMIT 1
    """,
    params=sales_period_params,
    columns=["product", "color", "size", "units_sold", "revenue"],
)
top_variant_label = "No variant sales yet"
if not top_variant.empty:
    top_variant_label = (
        f"{top_variant['product'].iloc[0]} | "
        f"Color: {top_variant['color'].iloc[0]} | "
        f"Size: {top_variant['size'].iloc[0]} | "
        f"Units: {fmt_int(top_variant['units_sold'].iloc[0])}"
    )

st.subheader("Executive Summary")
m1, m2, m3 = st.columns(3)
m4, m5, m6 = st.columns(3)
m1.metric("Revenue (KES)", fmt_int(revenue), delta=fmt_int(revenue_delta))
m2.metric("COGS (KES)", fmt_int(cost))
m3.metric("Gross Profit (KES)", fmt_int(gross_profit))
m4.metric("Operating Expenses (KES)", fmt_int(operating_exp))
m5.metric("Net After OPEX (KES)", fmt_int(net_after_ops))
m6.metric("Units Sold", fmt_int(units))
mx1, mx2, mx3, mx4 = st.columns(4)
mx1.metric("Total Products Sold", fmt_int(total_products_sold))
mx2.metric("Total Products Returned", fmt_int(total_products_returned))
mx3.metric("Total Products Exchanged", fmt_int(total_products_exchanged))
mx4.metric("Total Customers Served", fmt_int(total_customers_served))
ms1, ms2, ms3, ms4 = st.columns(4)
ms1.metric("Start of Month Total Products", fmt_int(opening_products))
ms2.metric("Start of Month Stock Value (KES)", fmt_int(opening_value))
ms3.metric("End of Month Total Products", fmt_int(closing_products))
ms4.metric("End of Month Stock Value (KES)", fmt_int(closing_value))
st.info(f"Most Sold Product: {top_product_name} ({fmt_int(top_product_units)} units)")
st.info(f"Most Sold Variant: {top_variant_label}")

with st.expander("Stock Value Checkpoints", expanded=False):
    stock_value_rows = pd.DataFrame(
        [
            {"Checkpoint": "Start of Month (OPENING)", "Total Products": opening_products, "Total Value of Products in Stock (KES)": opening_value},
            {"Checkpoint": "End of Month (CLOSING)", "Total Products": closing_products, "Total Value of Products in Stock (KES)": closing_value},
        ]
    )
    st.dataframe(stock_value_rows, hide_index=True, use_container_width=True)

summary_table = pd.DataFrame(
    [
        {"Metric": "Revenue (KES)", "Amount": fmt_int(revenue)},
        {"Metric": "COGS (KES)", "Amount": fmt_int(cost)},
        {"Metric": "Gross Profit (KES)", "Amount": fmt_int(gross_profit)},
        {"Metric": "Operating Expenses (KES)", "Amount": fmt_int(operating_exp)},
        {"Metric": "Net After OPEX (KES)", "Amount": fmt_int(net_after_ops)},
        {"Metric": "Ads Spend (KES)", "Amount": fmt_int(ads_spend)},
        {"Metric": "Total Products Sold", "Amount": fmt_int(total_products_sold)},
        {"Metric": "Total Products Returned", "Amount": fmt_int(total_products_returned)},
        {"Metric": "Total Products Exchanged", "Amount": fmt_int(total_products_exchanged)},
        {"Metric": "Total Customers Served", "Amount": fmt_int(total_customers_served)},
        {"Metric": "Start of Month Total Products", "Amount": fmt_int(opening_products)},
        {"Metric": "Start of Month Stock Value (KES)", "Amount": fmt_int(opening_value)},
        {"Metric": "End of Month Total Products", "Amount": fmt_int(closing_products)},
        {"Metric": "End of Month Stock Value (KES)", "Amount": fmt_int(closing_value)},
        {"Metric": "Most Sold Product", "Amount": f"{top_product_name} ({fmt_int(top_product_units)} units)"},
        {"Metric": "Most Sold Variant", "Amount": top_variant_label},
    ]
)
st.dataframe(summary_table, hide_index=True, use_container_width=True)

with st.expander("Sales Performance", expanded=False):
    top_styles = safe_query(
        conn,
        f"""
        SELECT
            (COALESCE(p.brand, 'Unknown') || ' ' || COALESCE(p.model, '')) AS style,
            COALESCE(SUM(ns.net_quantity), 0) AS units_sold,
            COALESCE(SUM(ns.net_revenue), 0) AS revenue,
            COALESCE(SUM(ns.net_cost), 0) AS cost,
            COUNT(DISTINCT p.id) AS variants
        FROM net_sales ns
        LEFT JOIN products p ON p.id = ns.product_id
        WHERE {ns_sales_period_clause}
          AND COALESCE(ns.notes, '') NOT LIKE '%Brokered Sale%'
        GROUP BY style
        ORDER BY units_sold DESC, revenue DESC
        LIMIT 10
        """,
        params=sales_period_params,
        columns=["style", "units_sold", "revenue", "cost", "variants"],
    )
    if top_styles.empty:
        st.info("No sales for this month.")
    else:
        top_styles["gross_profit"] = top_styles["revenue"] - top_styles["cost"]
        show = top_styles.rename(
            columns={
                "style": "Style",
                "units_sold": "Units Sold",
                "revenue": "Revenue (KES)",
                "cost": "COGS (KES)",
                "variants": "Color Variants",
                "gross_profit": "Gross Profit (KES)",
            }
        )
        for col in ["Revenue (KES)", "COGS (KES)", "Gross Profit (KES)"]:
            show[col] = show[col].map(lambda x: int(x))
        left_col, right_col = st.columns([1.15, 1], gap="large")
        with left_col:
            st.caption("Click a model row to load color breakdown.")
            selected_style = str(show["Style"].iloc[0])
            try:
                table_event = st.dataframe(
                    show,
                    hide_index=True,
                    use_container_width=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    key="monthly_top_styles_table",
                )
                selected_rows = table_event.selection.rows if table_event and table_event.selection else []
                if selected_rows:
                    selected_style = str(show.iloc[int(selected_rows[0])]["Style"])
            except TypeError:
                # Fallback for older Streamlit versions without row-selection events.
                st.dataframe(show, hide_index=True, use_container_width=True)
                style_options = show["Style"].tolist()
                selected_style = st.selectbox(
                    "Select a style for color/size breakdown",
                    style_options,
                    key="monthly_report_style_drilldown_fallback",
                )

        color_detail = safe_query(
            conn,
            f"""
            SELECT
                COALESCE(p.color, 'N/A') AS color,
                COALESCE(SUM(ns.net_quantity), 0) AS units_sold,
                COALESCE(SUM(ns.net_revenue), 0) AS revenue,
                COALESCE(SUM(ns.net_cost), 0) AS cost
            FROM net_sales ns
            LEFT JOIN products p ON p.id = ns.product_id
            WHERE {ns_sales_period_clause}
              AND (COALESCE(p.brand, 'Unknown') || ' ' || COALESCE(p.model, '')) = ?
              AND COALESCE(ns.notes, '') NOT LIKE '%Brokered Sale%'
            GROUP BY p.color
            ORDER BY units_sold DESC, revenue DESC
            """,
            params=tuple(list(sales_period_params) + [selected_style]),
            columns=["color", "units_sold", "revenue", "cost"],
        )
        with right_col:
            st.markdown(f"#### Model Detail: {selected_style}")
            if color_detail.empty:
                st.info("No color detail found for this model.")
            else:
                color_detail["gross_profit"] = color_detail["revenue"] - color_detail["cost"]
                color_show = color_detail.rename(
                    columns={
                        "color": "Color",
                        "units_sold": "Units Sold",
                        "revenue": "Revenue (KES)",
                        "cost": "COGS (KES)",
                        "gross_profit": "Gross Profit (KES)",
                    }
                )
                for col in ["Revenue (KES)", "COGS (KES)", "Gross Profit (KES)"]:
                    color_show[col] = color_show[col].map(lambda x: int(x))
                st.caption("Select a color to view size breakdown.")

                selected_color = str(color_show["Color"].iloc[0])
                try:
                    color_event = st.dataframe(
                        color_show,
                        hide_index=True,
                        use_container_width=True,
                        on_select="rerun",
                        selection_mode="single-row",
                        key="monthly_style_color_table",
                    )
                    color_rows = color_event.selection.rows if color_event and color_event.selection else []
                    if color_rows:
                        selected_color = str(color_show.iloc[int(color_rows[0])]["Color"])
                except TypeError:
                    st.dataframe(color_show, hide_index=True, use_container_width=True)
                    selected_color = st.selectbox(
                        "Select color for size breakdown",
                        color_show["Color"].tolist(),
                        key="monthly_report_color_drilldown_fallback",
                    )

                size_detail = safe_query(
                    conn,
                    f"""
                    SELECT
                        COALESCE(ns.size, 'N/A') AS size,
                        COALESCE(SUM(ns.net_quantity), 0) AS units_sold,
                        COALESCE(SUM(ns.net_revenue), 0) AS revenue,
                        COALESCE(SUM(ns.net_cost), 0) AS cost
                    FROM net_sales ns
                    LEFT JOIN products p ON p.id = ns.product_id
                    WHERE {ns_sales_period_clause}
                      AND (COALESCE(p.brand, 'Unknown') || ' ' || COALESCE(p.model, '')) = ?
                      AND COALESCE(p.color, 'N/A') = ?
                      AND COALESCE(ns.notes, '') NOT LIKE '%Brokered Sale%'
                    GROUP BY ns.size
                    ORDER BY units_sold DESC, revenue DESC
                    """,
                    params=tuple(list(sales_period_params) + [selected_style, selected_color]),
                    columns=["size", "units_sold", "revenue", "cost"],
                )

                st.markdown(f"##### Size Breakdown: {selected_color}")
                if size_detail.empty:
                    st.info("No size detail found for this color.")
                else:
                    size_detail["gross_profit"] = size_detail["revenue"] - size_detail["cost"]
                    size_show = size_detail.rename(
                        columns={
                            "size": "Size",
                            "units_sold": "Units Sold",
                            "revenue": "Revenue (KES)",
                            "cost": "COGS (KES)",
                            "gross_profit": "Gross Profit (KES)",
                        }
                    )
                    for col in ["Revenue (KES)", "COGS (KES)", "Gross Profit (KES)"]:
                        size_show[col] = size_show[col].map(lambda x: int(x))
                    st.dataframe(size_show, hide_index=True, use_container_width=True)

with st.expander("Customer Sources", expanded=False):
    sources_sales = safe_query(
        conn,
        f"""
        SELECT COALESCE(NULLIF(TRIM(source), ''), 'Unspecified') AS source, COUNT(*) AS count
        FROM sales
        WHERE {sales_period_clause}
        GROUP BY source
        ORDER BY count DESC
        """,
        params=sales_period_params,
        columns=["source", "count"],
    )
    sources_orders = safe_query(
        conn,
        f"""
        SELECT COALESCE(NULLIF(TRIM(source), ''), 'Unspecified') AS source, COUNT(*) AS count
        FROM online_orders
        WHERE {online_period_clause}
        GROUP BY source
        ORDER BY count DESC
        """,
        params=online_period_params,
        columns=["source", "count"],
    )
    sources = pd.concat([sources_sales, sources_orders], ignore_index=True)
    if sources.empty:
        st.info("No source data found.")
    else:
        breakdown = (
            sources.groupby("source")["count"]
            .sum()
            .reset_index()
            .sort_values(by="count", ascending=False)
            .rename(columns={"source": "Source", "count": "Count"})
        )
        st.dataframe(breakdown, hide_index=True, use_container_width=True)

    st.markdown("#### Source to Fulfillment")
    source_fulfillment = safe_query(
        conn,
        f"""
        SELECT
            COALESCE(NULLIF(TRIM(s.source), ''), 'Unspecified') AS source,
            COALESCE(NULLIF(TRIM(s.fulfillment_type), ''), 'Unspecified') AS fulfillment,
            COUNT(*) AS sales_count
        FROM sales s
        WHERE {s_sales_period_clause}
        GROUP BY source, fulfillment
        ORDER BY source, fulfillment
        """,
        params=sales_period_params,
        columns=["source", "fulfillment", "sales_count"],
    )
    if source_fulfillment.empty:
        st.info("No source/fulfillment data found.")
    else:
        sf_pivot = (
            source_fulfillment.pivot_table(
                index="source",
                columns="fulfillment",
                values="sales_count",
                aggfunc="sum",
                fill_value=0,
            )
            .reset_index()
            .rename(columns={"source": "Customer Source"})
        )
        sf_pivot.columns = [str(col) for col in sf_pivot.columns]
        for col in sf_pivot.columns:
            if col != "Customer Source":
                sf_pivot[col] = sf_pivot[col].map(lambda x: int(x))
        st.dataframe(sf_pivot, hide_index=True, use_container_width=True)

with st.expander("Delivery Operations", expanded=False):
    delivery_riders = safe_query(
        conn,
        f"""
        SELECT
            COALESCE(NULLIF(TRIM(delivery_option), ''), 'Unspecified') AS rider_or_courier,
            COUNT(*) AS trips
        FROM sales
        WHERE {sales_period_clause}
          AND COALESCE(fulfillment_type, '') = 'Delivery'
        GROUP BY rider_or_courier
        ORDER BY trips DESC
        """,
        params=sales_period_params,
        columns=["rider_or_courier", "trips"],
    )
    delivery_locations = safe_query(
        conn,
        f"""
        SELECT
            COALESCE(NULLIF(TRIM(delivery_location), ''), 'Unspecified') AS location,
            COUNT(*) AS trips
        FROM sales
        WHERE {sales_period_clause}
          AND COALESCE(fulfillment_type, '') = 'Delivery'
        GROUP BY location
        ORDER BY trips DESC
        """,
        params=sales_period_params,
        columns=["location", "trips"],
    )
    if delivery_riders.empty and delivery_locations.empty:
        st.info("No delivery records found for this month.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Trips by Rider/Courier")
            if delivery_riders.empty:
                st.info("No rider/courier delivery data.")
            else:
                st.dataframe(
                    delivery_riders.rename(columns={"rider_or_courier": "Rider/Courier", "trips": "Trips"}),
                    hide_index=True,
                    use_container_width=True,
                )
        with c2:
            st.markdown("#### Trips by Location")
            if delivery_locations.empty:
                st.info("No location delivery data.")
            else:
                st.dataframe(
                    delivery_locations.rename(columns={"location": "Location", "trips": "Trips"}),
                    hide_index=True,
                    use_container_width=True,
                )

with st.expander("Expenses", expanded=False):
    exp_rows = safe_query(
        conn,
        f"""
        SELECT expense_date, category, description, amount
        FROM operating_expenses
        WHERE {expense_period_clause}
        ORDER BY expense_date DESC
        """,
        params=expense_period_params,
        columns=["expense_date", "category", "description", "amount"],
    )
    if exp_rows.empty:
        st.info("No operating expenses recorded for this month.")
    else:
        exp_rows["amount"] = pd.to_numeric(exp_rows["amount"], errors="coerce").fillna(0)
        by_category = (
            exp_rows.groupby("category")["amount"]
            .sum()
            .reset_index()
            .sort_values(by="amount", ascending=False)
            .rename(columns={"category": "Category", "amount": "Amount (KES)"})
        )
        by_category["Amount (KES)"] = by_category["Amount (KES)"].map(lambda x: int(x))
        st.dataframe(by_category, hide_index=True, use_container_width=True)

        st.caption("Click any category below for line-by-line details.")
        for _, row in by_category.iterrows():
            category = str(row["Category"])
            with st.expander(f"{category} - KES {fmt_int(row['Amount (KES)'])}", expanded=False):
                detail = exp_rows[exp_rows["category"] == category].copy()
                detail["amount"] = detail["amount"].astype(int)
                st.dataframe(
                    detail.rename(
                        columns={
                            "expense_date": "Date",
                            "description": "Description",
                            "amount": "Amount (KES)",
                        }
                    )[["Date", "Description", "Amount (KES)"]],
                    hide_index=True,
                    use_container_width=True,
                )

with st.expander("Exceptions and Data Quality", expanded=False):
    missing_sales_source = safe_query(
        conn,
        f"""
        SELECT COUNT(*) AS cnt
        FROM sales
        WHERE {sales_period_clause}
          AND (source IS NULL OR TRIM(source) = '')
        """,
        params=sales_period_params,
        columns=["cnt"],
    )
    missing_delivery_location = safe_query(
        conn,
        f"""
        SELECT COUNT(*) AS cnt
        FROM sales
        WHERE {sales_period_clause}
          AND COALESCE(fulfillment_type, '') = 'Delivery'
          AND (delivery_location IS NULL OR TRIM(delivery_location) = '')
        """,
        params=sales_period_params,
        columns=["cnt"],
    )
    missing_source_count = int(missing_sales_source["cnt"].iloc[0] if not missing_sales_source.empty else 0)
    missing_delivery_loc_count = int(missing_delivery_location["cnt"].iloc[0] if not missing_delivery_location.empty else 0)
    q1, q2 = st.columns(2)
    q1.metric("Sales Missing Source", fmt_int(missing_source_count))
    q2.metric("Deliveries Missing Location", fmt_int(missing_delivery_loc_count))

st.subheader("Export")
pdf_col1, pdf_col2 = st.columns([1, 2])
with pdf_col1:
    generate_pdf = st.button(
        "Generate Monthly PDF",
        key="monthly_pdf_generate",
        disabled=not mandatory_checkpoints_complete,
    )
if not mandatory_checkpoints_complete:
    st.warning("PDF export is locked until all required stock takes for this month are completed.")

if generate_pdf:
    export_top_styles = safe_query(
        conn,
        f"""
        SELECT
            COALESCE(p.brand, 'Unknown') || ' ' || COALESCE(p.model, '') AS Style,
            COALESCE(p.color, 'N/A') AS Color,
            COALESCE(ns.size, 'N/A') AS Size,
            COALESCE(SUM(ns.net_quantity), 0) AS Units_Sold,
            COALESCE(SUM(ns.net_revenue), 0) AS Revenue_KES,
            COALESCE(SUM(ns.net_cost), 0) AS COGS_KES
        FROM net_sales ns
        LEFT JOIN products p ON p.id = ns.product_id
        WHERE {ns_sales_period_clause}
          AND COALESCE(ns.notes, '') NOT LIKE '%Brokered Sale%'
        GROUP BY ns.product_id, p.brand, p.model, p.color, ns.size
        ORDER BY Units_Sold DESC, Revenue_KES DESC
        LIMIT 25
        """,
        params=sales_period_params,
        columns=["Style", "Color", "Size", "Units_Sold", "Revenue_KES", "COGS_KES"],
    )

    export_sources = safe_query(
        conn,
        f"""
        SELECT COALESCE(NULLIF(TRIM(source), ''), 'Unspecified') AS Source, COUNT(*) AS Count
        FROM sales
        WHERE {sales_period_clause}
        GROUP BY Source
        ORDER BY Count DESC
        """,
        params=sales_period_params,
        columns=["Source", "Count"],
    )

    export_riders = safe_query(
        conn,
        f"""
        SELECT
            COALESCE(NULLIF(TRIM(delivery_option), ''), 'Unspecified') AS Rider_Courier,
            COUNT(*) AS Trips
        FROM sales
        WHERE {sales_period_clause}
          AND COALESCE(fulfillment_type, '') = 'Delivery'
        GROUP BY Rider_Courier
        ORDER BY Trips DESC
        """,
        params=sales_period_params,
        columns=["Rider_Courier", "Trips"],
    )

    export_locations = safe_query(
        conn,
        f"""
        SELECT
            COALESCE(NULLIF(TRIM(delivery_location), ''), 'Unspecified') AS Location,
            COUNT(*) AS Trips
        FROM sales
        WHERE {sales_period_clause}
          AND COALESCE(fulfillment_type, '') = 'Delivery'
        GROUP BY Location
        ORDER BY Trips DESC
        """,
        params=sales_period_params,
        columns=["Location", "Trips"],
    )

    export_expenses = safe_query(
        conn,
        f"""
        SELECT category AS Category, COALESCE(SUM(amount), 0) AS Amount_KES
        FROM operating_expenses
        WHERE {expense_period_clause}
        GROUP BY category
        ORDER BY Amount_KES DESC
        """,
        params=expense_period_params,
        columns=["Category", "Amount_KES"],
    )

    export_quality = pd.DataFrame(
        [
            {"Metric": "Sales Missing Source", "Count": int(missing_source_count)},
            {"Metric": "Deliveries Missing Location", "Count": int(missing_delivery_loc_count)},
        ]
    )

    try:
        period_file = (
            str(period_label)
            .replace(" ", "_")
            .replace(":", "")
            .replace("/", "-")
        )
        pdf_bytes = build_monthly_pdf_bytes(
            month_label=period_label,
            summary_df=summary_table,
            top_styles_df=export_top_styles,
            sources_df=export_sources,
            riders_df=export_riders,
            locations_df=export_locations,
            expenses_df=export_expenses,
            quality_df=export_quality,
        )
        with pdf_col2:
            st.download_button(
                "Download Monthly Report (PDF)",
                data=pdf_bytes,
                file_name=f"monthly_report_{period_file}.pdf",
                mime="application/pdf",
                key="monthly_pdf_download",
            )
    except Exception as e:
        st.error(f"Unable to generate PDF: {e}")

conn.close()

