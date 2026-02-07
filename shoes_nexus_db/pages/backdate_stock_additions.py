from db_config import DB_PATH
import streamlit as st
import sqlite3
import pandas as pd
from datetime import date

# ============================================
# DATABASE CONNECTION
# ============================================
def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# ============================================
# PAGE SETUP
# ============================================
st.set_page_config(page_title="Backdate Stock", layout="wide")
st.title("📦 Backdate Stock Additions")

# ============================================
# ACCESS CONTROL
# ============================================
if "role" not in st.session_state or st.session_state.role not in ["Admin", "Manager"]:
    st.error("⛔ Access Denied - Admin or Manager role required")
    st.stop()

st.info("ℹ️ Use this module to correct or add historical stock")

# ============================================
# STEP 1: DATE SELECTION
# ============================================
st.subheader("Step 1: Select Stock Arrival Date")

stock_date = st.date_input(
    "Stock Arrival Date",
    value=date.today(),
    max_value=date.today(),
    help="Cannot select future dates"
)

st.write(f"📅 Selected date: **{stock_date}**")

# ============================================
# STEP 2: PRODUCT SELECTION
# ============================================
st.subheader("Step 2: Select Product & Size")

conn = get_db()

products = pd.read_sql("""
    SELECT id, brand, model, color
    FROM products
    WHERE is_active = 1
    ORDER BY brand, model
""", conn)

if products.empty:
    st.warning("⚠️ No products in inventory")
    conn.close()
    st.stop()

products["display"] = (
    products["brand"] + " " +
    products["model"] + " (" +
    products["color"] + ")"
)

product_map = dict(zip(products["display"], products["id"]))
selected_product = st.selectbox("Select Product", product_map.keys())

product_id = product_map[selected_product]

# Get existing sizes for this product
sizes_df = pd.read_sql("""
    SELECT size, quantity
    FROM product_sizes
    WHERE product_id = ?
    ORDER BY size
""", conn, params=(product_id,))

if sizes_df.empty:
    st.warning("⚠️ No sizes exist for this product yet")
    st.info("💡 Enter a new size below to create it")
    size = st.text_input("Enter Size (e.g., 38, 40, 42)", key="new_size")
else:
    # Option to select existing or add new
    size_option = st.radio(
        "Size Selection",
        ["Select existing size", "Add new size"],
        horizontal=True
    )
    
    if size_option == "Select existing size":
        size = st.selectbox(
            "Select Size",
            sizes_df["size"],
            format_func=lambda x: f"Size {x} (Current Stock: {sizes_df[sizes_df['size']==x]['quantity'].values[0]})"
        )
    else:
        size = st.text_input("Enter New Size (e.g., 38, 40, 42)")

# ============================================
# STEP 3: QUANTITY
# ============================================
st.subheader("Step 3: Stock Details")

quantity = st.number_input(
    "Quantity to Add",
    min_value=1,
    step=1,
    value=1,
    help="Number of pairs received"
)

notes = st.text_area(
    "📝 Notes (optional)",
    placeholder="Source, supplier, or other remarks..."
)

# ============================================
# STEP 4: REVIEW & SUBMIT
# ============================================
st.subheader("Step 4: Review & Submit")

if size:
    st.info(f"""
    **Stock Addition Summary:**
    - Product: {selected_product}
    - Size: {size}
    - Quantity: +{quantity} pairs
    - Date: {stock_date}
    """)

    if st.button("➕ Add Stock", type="primary"):
        cur = conn.cursor()

        try:
            # Insert or update product_sizes
            cur.execute("""
                INSERT INTO product_sizes (product_id, size, quantity)
                VALUES (?, ?, ?)
                ON CONFLICT(product_id, size)
                DO UPDATE SET quantity = quantity + ?
            """, (int(product_id), str(size), int(quantity), int(quantity)))

            # Activity log
            cur.execute("""
                INSERT INTO activity_log
                (event_type, reference_id, role, username, message)
                VALUES (?, ?, ?, ?, ?)
            """, (
                "BACKDATE_STOCK",
                product_id,
                st.session_state.role,
                st.session_state.username,
                f"Added {quantity} pairs on {stock_date}: {selected_product} Size {size}. {notes}"
            ))

            conn.commit()
            
            st.success("✅ Stock updated successfully!")
            st.balloons()
            
            # Show new stock level
            cur.execute("""
                SELECT quantity FROM product_sizes
                WHERE product_id = ? AND size = ?
            """, (product_id, size))
            
            new_stock = cur.fetchone()[0]
            st.info(f"📦 New stock level for Size {size}: **{new_stock} pairs**")

        except Exception as e:
            conn.rollback()
            st.error(f"❌ Error: {e}")
        finally:
            conn.close()
else:
    st.warning("⚠️ Please enter a size")