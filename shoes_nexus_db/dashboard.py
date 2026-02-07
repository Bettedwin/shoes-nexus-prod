from db_config import DB_PATH
import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# ============================================
# ACCESS CONTROL
# ============================================
if st.session_state.get("role") != "Admin":
    st.warning("Access denied")
    st.stop()

# ============================================
# PAGE SETUP
# ============================================
st.set_page_config(page_title="Shoes Nexus Dashboard", layout="wide")

# ============================================
# CUSTOM CSS STYLING
# ============================================
st.markdown("""
    <style>
    /* Dashboard header */
    .dashboard-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        color: white;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    
    .dashboard-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    .dashboard-subtitle {
        font-size: 1.1rem;
        opacity: 0.9;
    }
    
    /* Metric cards */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
    }
    
    /* Section headers */
    .section-header {
        background: #f8f9fa;
        padding: 1rem 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #667eea;
        margin: 2rem 0 1rem 0;
    }
    
    .section-header h3 {
        margin: 0;
        color: #2c3e50;
    }
    
    /* Dataframe styling */
    .dataframe {
        border-radius: 10px;
        overflow: hidden;
    }
    
    /* Chart containers */
    .chart-container {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================
# DASHBOARD HEADER
# ============================================
st.markdown(f"""
    <div class="dashboard-header">
        <div class="dashboard-title">👟 Shoes Nexus Dashboard</div>
        <div class="dashboard-subtitle">Welcome back, {st.session_state.username} | {datetime.now().strftime("%B %d, %Y")}</div>
    </div>
""", unsafe_allow_html=True)

# ============================================
# DATABASE CONNECTION
# ============================================
conn = sqlite3.connect(DB_PATH)

# ============================================
# KEY METRICS ROW
# ============================================
st.markdown('<div class="section-header"><h3>📊 Key Metrics</h3></div>', unsafe_allow_html=True)

# Calculate key metrics
total_products = pd.read_sql("SELECT COUNT(*) as count FROM products WHERE is_active = 1", conn).iloc[0]['count']
total_sales = pd.read_sql("SELECT COUNT(*) as count FROM net_sales", conn).iloc[0]['count']
total_revenue = pd.read_sql("SELECT SUM(net_revenue) as total FROM net_sales", conn).iloc[0]['total'] or 0
total_profit = pd.read_sql("SELECT SUM(net_revenue - net_cost) as profit FROM net_sales", conn).iloc[0]['profit'] or 0

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="📦 Active Products",
        value=f"{total_products:,}",
        delta=None
    )

with col2:
    st.metric(
        label="🛒 Total Sales",
        value=f"{total_sales:,}",
        delta=None
    )

with col3:
    st.metric(
        label="💰 Total Revenue",
        value=f"KES {total_revenue:,.0f}",
        delta=None
    )

with col4:
    st.metric(
        label="📈 Total Profit",
        value=f"KES {total_profit:,.0f}",
        delta=None
    )

# ============================================
# INVENTORY SECTION
# ============================================
st.markdown('<div class="section-header"><h3>📦 Current Inventory</h3></div>', unsafe_allow_html=True)

products_df = pd.read_sql("SELECT * FROM products WHERE is_active = 1", conn)

if not products_df.empty:
    # Show inventory table
    st.dataframe(
        products_df,
        use_container_width=True,
        hide_index=True
    )
    
    # Low stock alert
    # Convert stock to integer first (safety check)
    products_df["stock"] = pd.to_numeric(products_df["stock"], errors='coerce').fillna(0).astype(int)

    # Now check low stock
    low_stock = products_df[products_df["stock"] <= 5]
    
    if not low_stock.empty:
        st.warning(f"⚠️ Low Stock Alert - {len(low_stock)} product(s) need restocking")
        st.dataframe(
            low_stock[['brand', 'model', 'color', 'stock']],
            use_container_width=True,
            hide_index=True
        )
else:
    st.info("No products in inventory")

# ============================================
# SALES SECTION
# ============================================
st.markdown('<div class="section-header"><h3>📊 Sales Overview</h3></div>', unsafe_allow_html=True)

sales_df = pd.read_sql("""
    SELECT 
        sale_id AS id,
        product_id,
        size,
        net_quantity AS quantity,
        net_revenue AS revenue,
        net_cost AS cost,
        payment_method,
        sale_date
    FROM net_sales
""", conn)

if not sales_df.empty:
    
    # Recent sales table
    with st.expander("📋 View Recent Sales", expanded=False):
        st.dataframe(
            sales_df.tail(20).sort_values('id', ascending=False),
            use_container_width=True,
            hide_index=True
        )
    
    # Calculate profit
    sales_df["profit"] = sales_df["revenue"] - sales_df["cost"]
    
    # ============================================
    # DAILY PERFORMANCE CHART
    # ============================================
    st.markdown('<div class="section-header"><h3>📈 Daily Business Performance</h3></div>', unsafe_allow_html=True)
    
    daily_profit = sales_df.groupby("sale_date").sum(numeric_only=True)
    
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(daily_profit.index, daily_profit["profit"], marker='o', linewidth=2, color='#667eea')
    ax.fill_between(daily_profit.index, daily_profit["profit"], alpha=0.3, color='#667eea')
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Profit (KES)", fontsize=12)
    ax.set_title("Daily Profit Trend", fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    st.pyplot(fig)
    
    # ============================================
    # BEST SELLERS
    # ============================================
    st.markdown('<div class="section-header"><h3>🔥 Best Selling Products</h3></div>', unsafe_allow_html=True)
    
    best_sellers = sales_df.groupby("product_id")["quantity"].sum().sort_values(ascending=False).head(10)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Bar chart of best sellers
        fig3, ax3 = plt.subplots(figsize=(10, 6))
        best_sellers.plot(kind='barh', ax=ax3, color='#764ba2')
        ax3.set_xlabel("Units Sold", fontsize=12)
        ax3.set_ylabel("Product ID", fontsize=12)
        ax3.set_title("Top 10 Products by Quantity", fontsize=14, fontweight='bold')
        plt.tight_layout()
        st.pyplot(fig3)
    
    with col2:
        # Table of best sellers
        st.dataframe(
            best_sellers.reset_index(),
            use_container_width=True,
            hide_index=True,
            column_config={
                "product_id": "Product ID",
                "quantity": "Units Sold"
            }
        )

else:
    st.info("No sales recorded yet.")

# ============================================
# MONTHLY SUMMARY
# ============================================
if not sales_df.empty:
    st.markdown('<div class="section-header"><h3>📅 Monthly Business Summary</h3></div>', unsafe_allow_html=True)
    
    monthly_summary = sales_df.copy()
    monthly_summary["month"] = monthly_summary["sale_date"].str[:7]
    monthly_report = monthly_summary.groupby("month").sum(numeric_only=True)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Monthly summary table
        st.dataframe(
            monthly_report[['revenue', 'cost', 'profit']],
            use_container_width=True,
            column_config={
                "revenue": st.column_config.NumberColumn("Revenue (KES)", format="KES %,.0f"),
                "cost": st.column_config.NumberColumn("Cost (KES)", format="KES %,.0f"),
                "profit": st.column_config.NumberColumn("Profit (KES)", format="KES %,.0f")
            }
        )
    
    with col2:
        # Monthly profit chart
        fig2, ax2 = plt.subplots(figsize=(10, 6))
        ax2.bar(monthly_report.index, monthly_report["profit"], color='#667eea', edgecolor='#764ba2', linewidth=1.5)
        ax2.set_xlabel("Month", fontsize=12)
        ax2.set_ylabel("Profit (KES)", fontsize=12)
        ax2.set_title("Monthly Profit", fontsize=14, fontweight='bold')
        ax2.grid(True, axis='y', alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        st.pyplot(fig2)

# ============================================
# CLOSE CONNECTION
# ============================================
conn.close()

# ============================================
# FOOTER
# ============================================
st.markdown("---")
st.markdown(
    '<p style="text-align: center; color: #95a5a6; font-size: 0.85rem;">Last updated: {}</p>'.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ),
    unsafe_allow_html=True
)