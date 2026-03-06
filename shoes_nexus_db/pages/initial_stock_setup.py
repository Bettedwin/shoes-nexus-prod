from db_config import DB_PATH
import streamlit as st
import sqlite3
import pandas as pd
from theme_admin import apply_admin_theme
from datetime import date
from ui_feedback import show_success_summary

# ============================================
# DATABASE CONNECTION
# ============================================
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# ============================================
# PAGE SETUP
# ============================================
st.set_page_config(page_title="Initial Stock Setup", layout="wide")
apply_admin_theme(
    "Initial Stock Setup",
    "Set up products, sizes, and opening stock.",
)

if not st.session_state.get("logged_in", False):
    st.warning("Session expired. Please log in again.")
    if st.button("Go to Login", key="initial_stock_go_login"):
        st.switch_page("app.py")
    st.stop()

# ============================================
# ACCESS CONTROL
# ============================================
if st.session_state.get("role") not in ["Admin", "Manager"]:
    st.error("⛔ Access Denied - Admin or Manager role required")
    st.stop()

# ============================================
# CUSTOM CSS
# ============================================
st.markdown("""
    <style>
    .setup-header {
        background: linear-gradient(135deg, #0b0b0f 0%, #c41224 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        color: white;
        box-shadow: 0 10px 30px rgba(11,11,15,0.2);
    }
    
    .setup-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    .setup-subtitle {
        font-size: 1.1rem;
        opacity: 0.9;
    }
    
    .product-card {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #e11d2a;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================
# HEADER
# ============================================
st.markdown("""
    <div class="setup-header">
        <div class="setup-title">📦 Initial Stock Setup</div>
        <div class="setup-subtitle">Add your existing inventory to the system</div>
    </div>
""", unsafe_allow_html=True)

# ============================================
# INSTRUCTIONS
# ============================================
with st.expander("📖 How to Use This Module", expanded=True):
    st.markdown("""
    ### Steps to Add Your Stock:
    
    1. **Select a product** from your existing product list
    2. **Enter the size** (e.g., 36, 38, 40, 42)
    3. **Enter quantity** you physically counted
    4. **Enter buying price** (what you paid for each pair)
    5. **Click "Add Stock"**
    6. **Repeat** for all products and sizes
    
    ### Important Notes:
    - ✅ You can add multiple sizes for the same product
    - ✅ Buying price is per unit (one pair)
    - ✅ This will ADD to existing stock (not replace)
    - ✅ All entries are logged for audit purposes
    """)

# ============================================
# MAIN TABS
# ============================================
tab1, tab2, tab3 = st.tabs(["➕ Add Stock", "📊 Current Stock", "📋 Stock Entry Log"])

# ============================================
# TAB 1: ADD STOCK
# ============================================
with tab1:
    st.subheader("Add Stock to Inventory")
    
    conn = get_db()
    
    # Get all products
    products_df = pd.read_sql("""
        SELECT id, brand, model, color, selling_price, buying_price
        FROM products
        WHERE is_active = 1
        ORDER BY brand, model
    """, conn)
    
    if products_df.empty:
        st.warning("⚠️ No products found. Please add products first in the main system.")
        conn.close()
        st.stop()
    
    # Create display names
    products_df["display"] = (
        products_df["brand"] + " " +
        products_df["model"] + " (" +
        products_df["color"] + ") - KES " +
        products_df["selling_price"].astype(str)
    )
    
    # Product selection
    product_map = dict(zip(products_df["display"], products_df["id"]))
    
    with st.form("stock_entry_form", clear_on_submit=False):
        st.markdown("### Product Information")
        
        selected_product = st.selectbox(
            "Select Product",
            product_map.keys(),
            help="Choose the product you're adding stock for"
        )
        
        product_id = product_map[selected_product]
        product = products_df[products_df["id"] == product_id].iloc[0]
        
        # Show product details
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Selling Price:** KES {product['selling_price']:,.0f}")
        with col2:
            current_buying_price = product['buying_price'] if pd.notna(product['buying_price']) else 0
            st.info(f"**Current Buying Price:** KES {current_buying_price:,.0f}")
        
        st.markdown("---")
        st.markdown("### Stock Details")
        
        # Size input
        col1, col2, col3 = st.columns(3)
        
        with col1:
            size = st.text_input(
                "Size *",
                placeholder="e.g., 38, 40, 42",
                help="Enter the shoe size"
            )
        
        with col2:
            quantity = st.number_input(
                "Quantity *",
                min_value=1,
                step=1,
                value=1,
                help="Number of pairs you counted"
            )
        
        with col3:
            buying_price = st.number_input(
                "Buying Price (per pair) *",
                min_value=0,
                step=10,
                value=int(current_buying_price) if current_buying_price > 0 else 0,
                help="What you paid for each pair"
            )
        
        notes = st.text_area(
            "Notes (optional)",
            placeholder="Supplier, batch number, or other remarks..."
        )
        
        # Entry date
        entry_date = st.date_input(
            "Stock Entry Date",
            value=date.today(),
            max_value=date.today(),
            help="When did you receive/count this stock?"
        )
        
        submit = st.form_submit_button("➕ Add Stock", type="primary", use_container_width=True)
        
        if submit:
            if not size.strip():
                st.error("⚠️ Please enter a size")
            elif quantity <= 0:
                st.error("⚠️ Quantity must be greater than 0")
            elif buying_price < 0:
                st.error("⚠️ Buying price cannot be negative")
            else:
                cur = conn.cursor()
                
                try:
                    # Insert or update product_sizes
                    cur.execute("""
                        INSERT INTO product_sizes (product_id, size, quantity)
                        VALUES (?, ?, ?)
                        ON CONFLICT(product_id, size)
                        DO UPDATE SET quantity = quantity + ?
                    """, (int(product_id), str(size.strip()), int(quantity), int(quantity)))
                    
                    # Update buying price in products table if different
                    if buying_price != current_buying_price:
                        cur.execute("""
                            UPDATE products
                            SET buying_price = ?
                            WHERE id = ?
                        """, (int(buying_price), int(product_id)))
                    
                    # Log the stock entry
                    cur.execute("""
                        INSERT INTO activity_log
                        (event_type, reference_id, role, username, message)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        "INITIAL_STOCK_ENTRY",
                        int(product_id),
                        st.session_state.role,
                        st.session_state.username,
                        f"Added {quantity} pairs - {selected_product}, Size {size}, BP: KES {buying_price}, Date: {entry_date}. {notes}"
                    ))
                    
                    conn.commit()
                    
                    show_success_summary(
                        "Stock added successfully.",
                        [
                            ("Product", selected_product),
                            ("Size", str(size)),
                            ("Quantity Added", int(quantity)),
                            ("Cost per Item (KES)", int(cost_per_item)),
                            ("New Stock Level", int(new_stock)),
                        ],
                    )
                                        
                    # Show summary
                    st.info(f"""
                    **Stock Entry Summary:**
                    - Product: {selected_product}
                    - Size: {size}
                    - Quantity Added: {quantity} pairs
                    - Buying Price: KES {buying_price:,} per pair
                    - Total Value: KES {quantity * buying_price:,}
                    - Entry Date: {entry_date}
                    """)
                    
                    # Get new stock level
                    cur.execute("""
                        SELECT quantity FROM product_sizes
                        WHERE product_id = ? AND size = ?
                    """, (product_id, size))
                    
                    new_stock = cur.fetchone()[0]
                    show_success_summary(
                        "Updated stock level confirmed.",
                        [
                            ("Size", str(size)),
                            ("Current Stock", int(new_stock)),
                        ],
                    )
                    
                except Exception as e:
                    conn.rollback()
                    st.error(f"❌ Error: {e}")
                finally:
                    conn.close()

# ============================================
# TAB 2: CURRENT STOCK VIEW
# ============================================
with tab2:
    st.subheader("Current Inventory Status")
    
    conn = get_db()
    
    # Get all stock
    stock_df = pd.read_sql("""
        SELECT 
            p.id,
            p.brand,
            p.model,
            p.color,
            ps.size,
            ps.quantity,
            p.buying_price,
            p.selling_price,
            (ps.quantity * p.buying_price) as stock_value
        FROM product_sizes ps
        JOIN products p ON p.id = ps.product_id
        WHERE p.is_active = 1 AND ps.quantity > 0
        ORDER BY p.brand, p.model, ps.size
    """, conn)
    
    conn.close()
    
    if stock_df.empty:
        st.info("📦 No stock entries yet. Use the 'Add Stock' tab to begin.")
    else:
        # Summary metrics
        total_pairs = stock_df["quantity"].sum()
        total_value = stock_df["stock_value"].sum()
        unique_products = stock_df["id"].nunique()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Pairs", f"{total_pairs:,}")
        with col2:
            st.metric("Total Stock Value", f"KES {total_value:,.0f}")
        with col3:
            st.metric("Unique Products", unique_products)
        
        st.markdown("---")
        
        # Stock table
        st.dataframe(
            stock_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": "ID",
                "brand": "Brand",
                "model": "Model",
                "color": "Color",
                "size": "Size",
                "quantity": st.column_config.NumberColumn("Quantity", format="%d pairs"),
                "buying_price": st.column_config.NumberColumn("Buying Price", format="KES %,.0f"),
                "selling_price": st.column_config.NumberColumn("Selling Price", format="KES %,.0f"),
                "stock_value": st.column_config.NumberColumn("Stock Value", format="KES %,.0f")
            }
        )
        
        # Download option
        st.markdown("---")
        csv = stock_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Stock Report (CSV)",
            data=csv,
            file_name=f"stock_report_{date.today()}.csv",
            mime="text/csv"
        )

# ============================================
# TAB 3: STOCK ENTRY LOG
# ============================================
with tab3:
    st.subheader("Stock Entry History")
    
    conn = get_db()
    
    # Get stock entry logs
    logs_df = pd.read_sql("""
        SELECT created_at, username, message
        FROM activity_log
        WHERE event_type = 'INITIAL_STOCK_ENTRY'
        ORDER BY created_at DESC
        LIMIT 100
    """, conn)

    
    conn.close()
    
    if logs_df.empty:
        st.info("No stock entries logged yet")
    else:
        st.dataframe(
            logs_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "timestamp": "Date & Time",
                "username": "Entered By",
                "message": "Details"
            }
        )
        
        st.info(f"📋 Showing last {len(logs_df)} stock entries")

# ============================================
# FOOTER
# ============================================
st.markdown("---")
st.markdown(
    '<p style="text-align: center; color: #95a5a6; font-size: 0.85rem;">Initial Stock Setup - Count and enter your physical inventory</p>',
    unsafe_allow_html=True
)
