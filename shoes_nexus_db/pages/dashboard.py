import calendar
import sqlite3
from datetime import date, datetime
import calendar as py_calendar

import pandas as pd
import streamlit as st

from db_config import DB_PATH
from theme_admin import apply_admin_theme


st.set_page_config(page_title="Shoes Nexus Dashboard", layout="wide")
apply_admin_theme("Dashboard", "Business performance and operations overview.")


if not st.session_state.get("logged_in", False):
    st.warning("Session expired. Please log in again.")
    if st.button("Go to Login", key="dashboard_go_login"):
        st.switch_page("app.py")
    st.stop()

if st.session_state.get("role") != "Admin":
    st.warning("Access denied")
    st.stop()


def month_bounds(year: int, month: int):
    start = pd.Timestamp(year=year, month=month, day=1)
    end = start + pd.offsets.MonthEnd(1)
    return start, end


def month_label(ts: pd.Timestamp) -> str:
    return ts.strftime("%B %Y")


def month_day_bounds(year: int, month: int, cutoff_day: int):
    start = pd.Timestamp(year=year, month=month, day=1)
    last_day = py_calendar.monthrange(int(year), int(month))[1]
    effective_day = max(1, min(int(cutoff_day), int(last_day)))
    end = pd.Timestamp(year=year, month=month, day=effective_day)
    return start, end, effective_day


def load_sales(conn, start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    df = pd.read_sql(
        """
        SELECT
            ns.sale_id,
            ns.product_id,
            COALESCE(p.brand, '') AS brand,
            COALESCE(p.model, '') AS model,
            COALESCE(p.color, '') AS color,
            COALESCE(ns.size, '') AS size,
            COALESCE(ns.net_quantity, 0) AS quantity,
            COALESCE(ns.net_revenue, 0) AS revenue,
            COALESCE(ns.net_cost, 0) AS cost,
            COALESCE(ns.payment_method, '') AS payment_method,
            COALESCE(ns.source, '') AS source,
            COALESCE(ns.sale_date, '') AS sale_date
        FROM net_sales ns
        LEFT JOIN products p ON p.id = ns.product_id
        WHERE date(ns.sale_date) BETWEEN date(?) AND date(?)
        ORDER BY ns.sale_id DESC
        """,
        conn,
        params=(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
    )
    if df.empty:
        return df
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce").fillna(0.0)
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce").fillna(0.0)
    df["profit"] = df["revenue"] - df["cost"]
    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
    return df


def summarize(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "revenue": 0.0,
            "cost": 0.0,
            "profit": 0.0,
            "units": 0,
            "sales_count": 0,
        }
    return {
        "revenue": float(df["revenue"].sum()),
        "cost": float(df["cost"].sum()),
        "profit": float((df["revenue"] - df["cost"]).sum()),
        "units": int(df["quantity"].sum()),
        "sales_count": int(df["sale_id"].nunique()),
    }


def render_summary_metrics(label: str, stats: dict):
    st.markdown(f"### {label}")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Revenue (KES)", f"{int(stats['revenue']):,}")
    c2.metric("COGS (KES)", f"{int(stats['cost']):,}")
    c3.metric("Gross Profit (KES)", f"{int(stats['profit']):,}")
    c4.metric("Units Sold", f"{int(stats['units']):,}")
    c5.metric("Sales Count", f"{int(stats['sales_count']):,}")


def render_inventory_overview(conn):
    inv = pd.read_sql(
        """
        SELECT
            COALESCE(p.brand, '') AS brand,
            COALESCE(p.model, '') AS model,
            COALESCE(p.color, '') AS color,
            COALESCE(ps.size, '') AS size,
            COALESCE(ps.quantity, 0) AS quantity
        FROM products p
        LEFT JOIN product_sizes ps ON ps.product_id = p.id
        WHERE COALESCE(p.is_active, 0) = 1
          AND COALESCE(ps.quantity, 0) >= 0
        ORDER BY p.brand, p.model, p.color, ps.size
        """,
        conn,
    )
    if inv.empty:
        st.info("No inventory records found.")
        return
    inv["quantity"] = pd.to_numeric(inv["quantity"], errors="coerce").fillna(0).astype(int)
    st.markdown("### Inventory Snapshot")
    c1, c2 = st.columns(2)
    c1.metric("Active Style-Color Lines", f"{int(inv[['brand','model','color']].drop_duplicates().shape[0]):,}")
    c2.metric("Total Units In Stock", f"{int(inv['quantity'].sum()):,}")
    low = inv[inv["quantity"] <= 2].copy()
    if not low.empty:
        with st.expander("Low Stock Lines (<= 2 units)", expanded=False):
            st.dataframe(low, use_container_width=True, hide_index=True)


def render_product_breakdown(df: pd.DataFrame, title: str):
    st.markdown(f"### {title}")
    if df.empty:
        st.info("No sales data for this period.")
        return

    top = (
        df.groupby(["brand", "model", "color"], as_index=False)
        .agg(units=("quantity", "sum"), revenue=("revenue", "sum"), cost=("cost", "sum"))
        .sort_values("units", ascending=False)
    )
    top["product"] = top["brand"] + " " + top["model"] + " (" + top["color"] + ")"

    c1, c2 = st.columns([1.7, 1.3])
    with c1:
        st.dataframe(
            top[["product", "units", "revenue", "cost"]].rename(
                columns={
                    "product": "Product",
                    "units": "Units Sold",
                    "revenue": "Revenue (KES)",
                    "cost": "COGS (KES)",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    with c2:
        st.bar_chart(top.set_index("product")[["units"]].head(10))


def render_daily_profit_chart(df: pd.DataFrame, title: str):
    st.markdown(f"### {title}")
    if df.empty:
        st.info("No daily trend available for this period.")
        return
    daily_src = df.copy()
    daily_src["sale_day"] = pd.to_datetime(daily_src["sale_date"], errors="coerce").dt.date
    daily_src = daily_src[daily_src["sale_day"].notna()]
    if daily_src.empty:
        st.info("No daily trend available for this period.")
        return
    daily = (
        daily_src.groupby("sale_day", as_index=False)
        .agg(revenue=("revenue", "sum"), cost=("cost", "sum"))
        .sort_values("sale_day")
    )
    daily["profit"] = daily["revenue"] - daily["cost"]
    daily = daily.set_index("sale_day")
    st.line_chart(daily[["revenue", "cost", "profit"]])


def render_recent_sales(df: pd.DataFrame):
    with st.expander("Recent Sales", expanded=False):
        if df.empty:
            st.info("No sales in this period.")
            return
        table = df.copy()
        table["sale_date"] = table["sale_date"].dt.strftime("%Y-%m-%d")
        st.dataframe(
            table[
                [
                    "sale_id",
                    "sale_date",
                    "brand",
                    "model",
                    "color",
                    "size",
                    "quantity",
                    "revenue",
                    "cost",
                    "payment_method",
                    "source",
                ]
            ].rename(
                columns={
                    "sale_id": "Sale ID",
                    "sale_date": "Date",
                    "brand": "Brand",
                    "model": "Model",
                    "color": "Color",
                    "size": "Size",
                    "quantity": "Qty",
                    "revenue": "Revenue (KES)",
                    "cost": "COGS (KES)",
                    "payment_method": "Payment",
                    "source": "Source",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )


def month_step(year: int, month: int, delta: int):
    m = month + delta
    y = year
    while m < 1:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return y, m


conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute("PRAGMA foreign_keys = ON")
today = pd.Timestamp.today()

if "dash_month_year" not in st.session_state:
    st.session_state["dash_month_year"] = int(today.year)
if "dash_month_num" not in st.session_state:
    st.session_state["dash_month_num"] = int(today.month)

st.caption(f"Welcome back, {st.session_state.get('username', 'admin')} | {datetime.now().strftime('%B %d, %Y')}")

mode = st.radio(
    "Dashboard Period Mode",
    ["Single Month", "Month Comparison", "MTD Same-Day Pace", "Multi-Month Range"],
    horizontal=True,
    key="dashboard_period_mode",
)

if mode == "Single Month":
    n1, n2, n3, n4 = st.columns([0.8, 1.4, 1.4, 0.8])
    with n1:
        if st.button("Prev Month", key="dash_prev_month", use_container_width=True):
            y, m = month_step(st.session_state["dash_month_year"], st.session_state["dash_month_num"], -1)
            st.session_state["dash_month_year"] = y
            st.session_state["dash_month_num"] = m
            st.rerun()
    with n2:
        selected_year = st.selectbox(
            "Year",
            list(range(max(2020, int(today.year) - 5), int(today.year) + 2)),
            index=list(range(max(2020, int(today.year) - 5), int(today.year) + 2)).index(st.session_state["dash_month_year"]),
            key="dash_year_select",
        )
    with n3:
        selected_month = st.selectbox(
            "Month",
            list(range(1, 13)),
            format_func=lambda x: calendar.month_name[x],
            index=int(st.session_state["dash_month_num"]) - 1,
            key="dash_month_select",
        )
    with n4:
        if st.button("Next Month", key="dash_next_month", use_container_width=True):
            y, m = month_step(st.session_state["dash_month_year"], st.session_state["dash_month_num"], 1)
            st.session_state["dash_month_year"] = y
            st.session_state["dash_month_num"] = m
            st.rerun()

    st.session_state["dash_month_year"] = int(selected_year)
    st.session_state["dash_month_num"] = int(selected_month)
    start, end = month_bounds(st.session_state["dash_month_year"], st.session_state["dash_month_num"])

    sales = load_sales(conn, start, end)
    render_summary_metrics(month_label(start), summarize(sales))
    render_daily_profit_chart(sales, "Daily Revenue, COGS and Profit")
    render_product_breakdown(sales, "Top Sold Product Variants")
    render_recent_sales(sales)
    render_inventory_overview(conn)

elif mode == "Month Comparison":
    base_year = int(today.year)
    years = list(range(max(2020, base_year - 5), base_year + 2))
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        y_a = st.selectbox("Month A Year", years, index=years.index(base_year), key="dash_cmp_y_a")
    with c2:
        m_a = st.selectbox("Month A", list(range(1, 13)), format_func=lambda x: calendar.month_name[x], index=max(0, int(today.month) - 1), key="dash_cmp_m_a")
    with c3:
        y_b = st.selectbox("Month B Year", years, index=years.index(base_year), key="dash_cmp_y_b")
    with c4:
        m_b = st.selectbox("Month B", list(range(1, 13)), format_func=lambda x: calendar.month_name[x], index=max(0, int(today.month) - 2), key="dash_cmp_m_b")

    s_a, e_a = month_bounds(int(y_a), int(m_a))
    s_b, e_b = month_bounds(int(y_b), int(m_b))

    df_a = load_sales(conn, s_a, e_a)
    df_b = load_sales(conn, s_b, e_b)
    sum_a = summarize(df_a)
    sum_b = summarize(df_b)

    st.markdown("### Month by Month Comparison")
    cmp_df = pd.DataFrame(
        [
            {"Metric": "Revenue (KES)", month_label(s_a): int(sum_a["revenue"]), month_label(s_b): int(sum_b["revenue"]), "Delta (B-A)": int(sum_b["revenue"] - sum_a["revenue"])},
            {"Metric": "COGS (KES)", month_label(s_a): int(sum_a["cost"]), month_label(s_b): int(sum_b["cost"]), "Delta (B-A)": int(sum_b["cost"] - sum_a["cost"])},
            {"Metric": "Gross Profit (KES)", month_label(s_a): int(sum_a["profit"]), month_label(s_b): int(sum_b["profit"]), "Delta (B-A)": int(sum_b["profit"] - sum_a["profit"])},
            {"Metric": "Units Sold", month_label(s_a): int(sum_a["units"]), month_label(s_b): int(sum_b["units"]), "Delta (B-A)": int(sum_b["units"] - sum_a["units"])},
            {"Metric": "Sales Count", month_label(s_a): int(sum_a["sales_count"]), month_label(s_b): int(sum_b["sales_count"]), "Delta (B-A)": int(sum_b["sales_count"] - sum_a["sales_count"])},
        ]
    )
    st.dataframe(cmp_df, use_container_width=True, hide_index=True)

    st.markdown("### Top Variants by Month")
    left, right = st.columns(2)
    with left:
        render_product_breakdown(df_a, month_label(s_a))
    with right:
        render_product_breakdown(df_b, month_label(s_b))

elif mode == "MTD Same-Day Pace":
    st.markdown("### Month-to-Date Same-Day Pace")
    st.caption("Compare each month up to the same day-of-month cutoff (fair mid-month comparison).")

    base_year = int(today.year)
    years = list(range(max(2020, base_year - 5), base_year + 2))
    c1, c2, c3 = st.columns(3)
    with c1:
        y_base = st.selectbox("Base Year", years, index=years.index(base_year), key="dash_mtd_base_year")
    with c2:
        m_base = st.selectbox(
            "Base Month",
            list(range(1, 13)),
            format_func=lambda x: calendar.month_name[x],
            index=max(0, int(today.month) - 1),
            key="dash_mtd_base_month",
        )
    with c3:
        cutoff_day = st.number_input(
            "Cutoff Day",
            min_value=1,
            max_value=31,
            value=min(31, int(today.day)),
            step=1,
            key="dash_mtd_cutoff_day",
        )

    compare_count = st.slider("Months to compare (including base month)", min_value=2, max_value=6, value=4, step=1, key="dash_mtd_compare_count")

    # Build month list from oldest -> newest ending at base month.
    month_pairs = []
    y_tmp, m_tmp = int(y_base), int(m_base)
    for _ in range(int(compare_count)):
        month_pairs.append((y_tmp, m_tmp))
        y_tmp, m_tmp = month_step(y_tmp, m_tmp, -1)
    month_pairs = list(reversed(month_pairs))

    rows = []
    for y, m in month_pairs:
        s, e, eff = month_day_bounds(y, m, int(cutoff_day))
        df_m = load_sales(conn, s, e)
        sm = summarize(df_m)
        days = max(1, int(eff))
        rows.append(
            {
                "Month": month_label(s),
                "Year": int(y),
                "MonthNum": int(m),
                "Cutoff Day Requested": int(cutoff_day),
                "Cutoff Day Used": int(eff),
                "Revenue (KES)": int(sm["revenue"]),
                "COGS (KES)": int(sm["cost"]),
                "Gross Profit (KES)": int(sm["profit"]),
                "Units Sold": int(sm["units"]),
                "Sales Count": int(sm["sales_count"]),
                "Avg Revenue/Day (KES)": int(sm["revenue"] / days),
                "Avg Units/Day": round(float(sm["units"]) / float(days), 2),
            }
        )

    pace_df = pd.DataFrame(rows)
    if pace_df.empty:
        st.info("No sales data found for selected MTD pace range.")
    else:
        latest = pace_df.iloc[-1].copy()
        prev = pace_df.iloc[-2].copy() if len(pace_df) >= 2 else None

        st.markdown("#### Current vs Previous (Same-Day Cutoff)")
        k1, k2, k3, k4, k5 = st.columns(5)
        if prev is not None and int(prev["Revenue (KES)"]) != 0:
            delta_rev_pct = ((int(latest["Revenue (KES)"]) - int(prev["Revenue (KES)"])) / float(prev["Revenue (KES)"])) * 100.0
        else:
            delta_rev_pct = 0.0
        if prev is not None and int(prev["Gross Profit (KES)"]) != 0:
            delta_gp_pct = ((int(latest["Gross Profit (KES)"]) - int(prev["Gross Profit (KES)"])) / float(prev["Gross Profit (KES)"])) * 100.0
        else:
            delta_gp_pct = 0.0
        k1.metric("Revenue (KES)", f"{int(latest['Revenue (KES)']):,}", delta=f"{delta_rev_pct:+.1f}% vs prev")
        k2.metric("COGS (KES)", f"{int(latest['COGS (KES)']):,}")
        k3.metric("Gross Profit (KES)", f"{int(latest['Gross Profit (KES)']):,}", delta=f"{delta_gp_pct:+.1f}% vs prev")
        k4.metric("Units Sold", f"{int(latest['Units Sold']):,}")
        k5.metric("Sales Count", f"{int(latest['Sales Count']):,}")

        st.markdown("#### MTD Pace Table")
        st.dataframe(
            pace_df[
                [
                    "Month",
                    "Cutoff Day Requested",
                    "Cutoff Day Used",
                    "Revenue (KES)",
                    "COGS (KES)",
                    "Gross Profit (KES)",
                    "Units Sold",
                    "Sales Count",
                    "Avg Revenue/Day (KES)",
                    "Avg Units/Day",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        chart_df = pace_df.set_index("Month")[["Revenue (KES)", "COGS (KES)", "Gross Profit (KES)"]]
        st.markdown("#### MTD Trend (Same-Day Cutoff)")
        st.line_chart(chart_df)

        # Optional month drilldown selection
        st.markdown("#### Drilldown by Month")
        month_choice = st.selectbox("Select month to inspect", pace_df["Month"].tolist(), key="dash_mtd_drill_month")
        picked = pace_df[pace_df["Month"] == month_choice].iloc[0]
        s, e, _ = month_day_bounds(int(picked["Year"]), int(picked["MonthNum"]), int(cutoff_day))
        df_pick = load_sales(conn, s, e)
        render_product_breakdown(df_pick, f"Top Sold Product Variants - {month_choice} (MTD)")
        render_recent_sales(df_pick)

else:
    c1, c2 = st.columns(2)
    with c1:
        range_start = st.date_input("Range Start (month)", value=date(today.year, max(1, today.month - 2), 1), key="dash_range_start")
    with c2:
        range_end = st.date_input("Range End (month)", value=date(today.year, today.month, 1), key="dash_range_end")

    start_month = pd.Timestamp(range_start.year, range_start.month, 1)
    end_month = pd.Timestamp(range_end.year, range_end.month, 1) + pd.offsets.MonthEnd(1)
    if start_month > end_month:
        st.error("Range start must be before range end.")
    else:
        sales = load_sales(conn, start_month, end_month)
        render_summary_metrics(f"{month_label(start_month)} to {month_label(end_month)}", summarize(sales))

        if sales.empty:
            st.info("No sales found for selected multi-month range.")
        else:
            sales["month_key"] = sales["sale_date"].dt.strftime("%Y-%m")
            month_rollup = (
                sales.groupby("month_key", as_index=False)
                .agg(revenue=("revenue", "sum"), cost=("cost", "sum"), units=("quantity", "sum"))
                .sort_values("month_key")
            )
            month_rollup["profit"] = month_rollup["revenue"] - month_rollup["cost"]
            st.markdown("### Multi-Month Trend")
            st.line_chart(month_rollup.set_index("month_key")[["revenue", "cost", "profit"]])
            st.dataframe(
                month_rollup.rename(
                    columns={
                        "month_key": "Month",
                        "revenue": "Revenue (KES)",
                        "cost": "COGS (KES)",
                        "profit": "Gross Profit (KES)",
                        "units": "Units Sold",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
            render_product_breakdown(sales, "Top Variants Across Selected Months")
            render_recent_sales(sales)

conn.close()

