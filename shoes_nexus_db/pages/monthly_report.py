from db_config import DB_PATH
import sqlite3
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Monthly Report", layout="wide")
st.title("📅 Monthly Report")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

month = st.date_input("Select Month", pd.Timestamp.today())
month_str = month.strftime("%Y-%m")

cursor.execute("""
SELECT COALESCE(SUM(net_revenue), 0), COALESCE(SUM(net_cost), 0)
FROM net_sales
WHERE strftime('%Y-%m', sale_date) = ?
""", (month_str,))
revenue, cost = cursor.fetchone()

cursor.execute("""
SELECT COALESCE(SUM(amount), 0)
FROM daily_expenses
WHERE strftime('%Y-%m', expense_date) = ?
""", (month_str,))
ads_spend = cursor.fetchone()[0] or 0

cursor.execute("""
SELECT COALESCE(SUM(amount), 0)
FROM home_expenses
WHERE strftime('%Y-%m', expense_date) = ?
""", (month_str,))
home_expenses = cursor.fetchone()[0] or 0

gross_profit = revenue - cost

st.subheader("Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Revenue (KES)", int(revenue))
col2.metric("COGS (KES)", int(cost))
col3.metric("Gross Profit (KES)", int(gross_profit))
col4.metric("Ads Spend (KES)", int(ads_spend))

st.subheader("Home Expenses (KES)")
st.metric("Total Home Expenses", int(home_expenses))

st.subheader("Business Expenses by Category (Monthly)")
df_business = pd.read_sql(
    """
    SELECT category, amount
    FROM operating_expenses
    WHERE strftime('%Y-%m', expense_date) = ?
    """,
    conn,
    params=(month_str,)
)
if df_business.empty:
    st.info("No business expenses recorded for this month.")
else:
    df_business["amount"] = pd.to_numeric(df_business["amount"], errors="coerce").fillna(0)
    breakdown = (
        df_business.groupby("category")["amount"]
        .sum()
        .reset_index()
        .sort_values(by="amount", ascending=False)
    )
    st.dataframe(
        breakdown.rename(columns={"category": "Category", "amount": "Amount (KES)"}),
        hide_index=True,
        use_container_width=True
    )

st.subheader("Home Expenses by Category (Monthly)")
df_home = pd.read_sql(
    """
    SELECT category, amount
    FROM home_expenses
    WHERE strftime('%Y-%m', expense_date) = ?
    """,
    conn,
    params=(month_str,)
)
if df_home.empty:
    st.info("No home expenses recorded for this month.")
else:
    df_home["amount"] = pd.to_numeric(df_home["amount"], errors="coerce").fillna(0)
    home_breakdown = (
        df_home.groupby("category")["amount"]
        .sum()
        .reset_index()
        .sort_values(by="amount", ascending=False)
    )
    st.dataframe(
        home_breakdown.rename(columns={"category": "Category", "amount": "Amount (KES)"}),
        hide_index=True,
        use_container_width=True
    )

st.subheader("Customer Sources (Monthly)")
try:
    df_sources_sales = pd.read_sql(
        """
        SELECT source, COUNT(*) AS count
        FROM sales
        WHERE strftime('%Y-%m', sale_date) = ?
        GROUP BY source
        """,
        conn,
        params=(month_str,)
    )
except Exception:
    df_sources_sales = pd.DataFrame(columns=["source", "count"])

try:
    df_sources_orders = pd.read_sql(
        """
        SELECT source, COUNT(*) AS count
        FROM online_orders
        WHERE strftime('%Y-%m', created_at) = ?
        GROUP BY source
        """,
        conn,
        params=(month_str,)
    )
except Exception:
    df_sources_orders = pd.DataFrame(columns=["source", "count"])

df_sources = pd.concat([df_sources_sales, df_sources_orders], ignore_index=True)
if not df_sources.empty:
    df_sources["source"] = df_sources["source"].fillna("").astype(str).str.strip()

# Count missing/legacy sources
missing_sales = 0
missing_orders = 0
try:
    missing_sales = pd.read_sql(
        """
        SELECT COUNT(*) AS count
        FROM sales
        WHERE strftime('%Y-%m', sale_date) = ?
          AND (source IS NULL OR TRIM(source) = '')
        """,
        conn,
        params=(month_str,)
    )["count"].iloc[0] or 0
except Exception:
    missing_sales = 0

try:
    missing_orders = pd.read_sql(
        """
        SELECT COUNT(*) AS count
        FROM online_orders
        WHERE strftime('%Y-%m', created_at) = ?
          AND (source IS NULL OR TRIM(source) = '')
        """,
        conn,
        params=(month_str,)
    )["count"].iloc[0] or 0
except Exception:
    missing_orders = 0

missing_total = int(missing_sales + missing_orders)

df_sources = df_sources[df_sources["source"] != ""]
breakdown = (
    df_sources.groupby("source")["count"]
    .sum()
    .reset_index()
    .sort_values(by="count", ascending=False)
)
breakdown.rename(columns={"source": "Source", "count": "Count"}, inplace=True)

if missing_total > 0:
    # Apply legacy distribution to historical (missing) records only
    insta = int(missing_total * 0.4)
    tiktok = int(missing_total * 0.4)
    remaining = missing_total - insta - tiktok
    referrals = remaining // 2
    walkins = remaining - referrals

    legacy_rows = pd.DataFrame([
        {"Source": "Instagram (Legacy)", "Count": insta},
        {"Source": "TikTok (Legacy)", "Count": tiktok},
        {"Source": "Referrals (Legacy)", "Count": referrals},
        {"Source": "In-store Walkins (Legacy)", "Count": walkins}
    ])
    breakdown = pd.concat([breakdown, legacy_rows], ignore_index=True)
    st.info(
        "Legacy distribution applied only to historical records with missing source."
    )

if breakdown.empty:
    st.info("No customer source data recorded for this month.")
else:
    st.dataframe(breakdown, hide_index=True, use_container_width=True)

conn.close()
