from db_config import DB_PATH
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date

# ============================================
# DATABASE CONNECTION
# ============================================
def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def ensure_sales_source_column():
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE sales ADD COLUMN source TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def get_or_create_brokered_product():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM products
        WHERE category = 'External' AND brand = 'Brokered' AND model = 'Brokered Sale'
        LIMIT 1
    """)
    row = cur.fetchone()
    if row:
        conn.close()
        return int(row[0])
    cur.execute("""
        INSERT INTO products (category, brand, model, color, buying_price, selling_price, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    """, ("External", "Brokered", "Brokered Sale", "N/A", 0, 0))
    brokered_id = cur.lastrowid
    conn.commit()
    conn.close()
    return int(brokered_id)

# ============================================
# PAGE SETUP
# ============================================
st.set_page_config(page_title="Backdate Sales", layout="wide")
st.title("📅 Backdate Historical Sales")

# ============================================
# CHECK USER ROLE (Only Admin/Manager allowed)
# ============================================
if "role" not in st.session_state or st.session_state.role not in ["Admin", "Manager"]:
    st.error("⛔ Access Denied - Admin or Manager role required")
    st.stop()

ensure_sales_source_column()

st.info("ℹ️ Use this module to enter historical sales data")

# ============================================
# STEP 1: SELECT DATE
# ============================================
st.subheader("Step 1: Select Sale Date")

today = date.today()

# Date picker - blocks future dates
sale_date = st.date_input(
    "Select the date of sale",
    value=today,
    max_value=today,  # This prevents selecting future dates
    help="You cannot select future dates"
)

st.write(f"📅 Selected date: **{sale_date}**")

# ============================================
# STEP 2: LOAD AVAILABLE PRODUCTS
# ============================================
st.subheader("Step 2: Select Product & Size")

conn = get_db()

# Get all active products
products_df = pd.read_sql("""
    SELECT 
        p.id,
        p.brand,
        p.model,
        p.color,
        p.selling_price,
        p.buying_price
    FROM products p
    WHERE p.is_active = 1
    ORDER BY p.brand, p.model
""", conn)

if products_df.empty:
    st.warning("⚠️ No products in inventory")
    conn.close()
    st.stop()

# Create display names for products
products_df["display"] = (
    products_df["brand"] + " " +
    products_df["model"] + " (" +
    products_df["color"] + ") - KES " +
    products_df["selling_price"].astype(str)
)

# Product selection dropdown
product_map = dict(zip(products_df["display"], products_df["id"]))
selected_product = st.selectbox("Select Product", product_map.keys())

product_id = product_map[selected_product]
product = products_df[products_df["id"] == product_id].iloc[0]

st.write(f"💰 Selling Price: **KES {product['selling_price']}**")

# Get available sizes for this product
sizes_df = pd.read_sql("""
    SELECT size, quantity
    FROM product_sizes
    WHERE product_id = ?
    ORDER BY size
""", conn, params=(product_id,))

if sizes_df.empty:
    st.warning("⚠️ No sizes configured for this product")
    st.info("💡 Please add sizes in inventory management first")
    conn.close()
    st.stop()

# Size selection
size = st.selectbox(
    "Select Size",
    sizes_df["size"],
    format_func=lambda x: f"Size {x} (Stock: {sizes_df[sizes_df['size']==x]['quantity'].values[0]})"
)

available_stock = sizes_df[sizes_df["size"] == size]["quantity"].values[0]

# Show stock warning
if available_stock <= 0:
    st.error(f"❌ No stock available for size {size}")
    st.info("💡 You may need to add stock first using the backdate stock module")
    # Don't stop - allow admin to record sale anyway (they'll fix stock later)
else:
    st.success(f"✅ Available stock: {available_stock} pairs")

# ============================================
# STEP 3: SALE DETAILS
# ============================================
st.subheader("Step 3: Sale Details")

sale_type = st.radio(
    "Sale Type",
    ["Regular Sale", "Brokered Sale (Profit Only)"],
    horizontal=True
)
if sale_type == "Brokered Sale (Profit Only)":
    st.info("Brokered sale ignores selected product/size and records profit-only.")

col1, col2 = st.columns(2)

with col1:
    quantity = st.number_input(
        "Quantity Sold",
        min_value=1,
        step=1,
        value=1
    )

with col2:
    payment_method = st.selectbox(
        "Payment Method",
        ["Cash", "M-Pesa Paybill"]
    )

source = st.selectbox(
    "Customer Source",
    ["Instagram", "TikTok", "Walk-in", "Website", "Twitter", "Referral", "Other"]
)
source_other = ""
if source == "Other":
    source_other = st.text_input("Specify Source")

# Optional notes
notes = st.text_area(
    "📝 Notes (optional)",
    placeholder="Any remarks about this sale...",
    help="Example: Repeat customer, Walk-in, etc."
)

broker_profit = 0
if sale_type == "Brokered Sale (Profit Only)":
    broker_profit = st.number_input(
        "Profit per item (KES)",
        min_value=0,
        step=50,
        value=0
    )

# ============================================
# STEP 4: CALCULATE TOTALS
# ============================================
st.subheader("Step 4: Review & Submit")

if sale_type == "Brokered Sale (Profit Only)":
    revenue = int(broker_profit) * int(quantity)
    cost = 0
else:
    revenue = int(product['selling_price']) * quantity
    cost = int(product['buying_price']) * quantity
profit = revenue - cost

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Revenue", f"KES {revenue:,}")

with col2:
    st.metric("Cost", f"KES {cost:,}")

with col3:
    st.metric("Profit", f"KES {profit:,}")

# ============================================
# STEP 5: SUBMIT SALE
# ============================================
if st.button("💾 Record Historical Sale", type="primary"):
    
    cur = conn.cursor()
    
    try:
        source_value = source_other.strip() if source == "Other" else source

        if sale_type == "Brokered Sale (Profit Only)":
            brokered_product_id = get_or_create_brokered_product()
            cur.execute("""
                INSERT INTO sales 
                (product_id, size, quantity, revenue, cost, payment_method, source, sale_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(brokered_product_id),
                "N/A",
                int(quantity),
                int(revenue),
                int(cost),
                str(payment_method),
                str(source_value),
                str(sale_date),
                f"Brokered Sale | {notes}".strip()
            ))
        else:
            # 1. Check if enough stock (warning only, don't block)
            cur.execute("""
                SELECT quantity FROM product_sizes
                WHERE product_id = ? AND size = ?
            """, (product_id, size))
            
            stock_row = cur.fetchone()
            current_stock = stock_row[0] if stock_row else 0
            
            if quantity > current_stock:
                st.warning(f"⚠️ Recording sale of {quantity} but only {current_stock} in stock. You may need to backdate stock addition.")
            
            # 2. Insert the sale with the selected historical date
            cur.execute("""
                INSERT INTO sales 
                (product_id, size, quantity, revenue, cost, payment_method, source, sale_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(product_id),
                str(size),
                int(quantity),
                int(revenue),
                int(cost),
                str(payment_method),
                str(source_value),
                str(sale_date),  # Historical date selected by user
                notes
            ))
        
        sale_id = cur.lastrowid
        
        # 3. Deduct from stock (regular sales only)
        if sale_type != "Brokered Sale (Profit Only)":
            cur.execute("""
                UPDATE product_sizes
                SET quantity = quantity - ?
                WHERE product_id = ? AND size = ?
            """, (int(quantity), int(product_id), str(size)))
        
        # 4. Activity log
        cur.execute("""
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "BACKDATE_SALE",
            sale_id,
            st.session_state.role,
            st.session_state.username,
            f"Backdated sale to {sale_date}: {selected_product if sale_type != 'Brokered Sale (Profit Only)' else 'Brokered Sale'}, Qty {quantity}"
        ))
        
        conn.commit()
        
        st.success(f"✅ Sale recorded successfully for {sale_date}!")
        st.balloons()
        
        st.info(f"""
        **Sale Summary:**
        - Date: {sale_date}
        - Product: {selected_product}
        - Size: {size}
        - Quantity: {quantity}
        - Revenue: KES {revenue:,}
        - Payment: {payment_method}
        """)
        
    except Exception as e:
        conn.rollback()
        st.error(f"❌ Error recording sale: {e}")
    finally:
        conn.close()
