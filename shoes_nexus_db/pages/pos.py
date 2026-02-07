from db_config import DB_PATH
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# ----------------------------
# PAGE SETUP
# ----------------------------
st.set_page_config(page_title="Shoes Nexus POS", layout="centered")
st.title("🧾 Shoes Nexus POS System")

# ----------------------------
# DATABASE CONNECTION
# ----------------------------
def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# ----------------------------
# LOAD PRODUCTS
# ----------------------------
conn = get_db()
products_df = pd.read_sql("SELECT * FROM products", conn)
conn.close()

if products_df.empty:
    st.warning("No products in inventory.")
    st.stop()

products_df["display"] = (
    products_df["brand"] + " " +
    products_df["model"] + " (" +
    products_df["color"] + ")"
)

product_map = dict(zip(products_df["display"], products_df["id"]))

# ----------------------------
# PRODUCT SELECTION
# ----------------------------
selected_product = st.selectbox("Select Product", product_map.keys())
product_id = product_map[selected_product]

product = products_df[products_df["id"] == product_id].iloc[0]

sell_price = int(product["selling_price"])
buy_price = product["buying_price"]
missing_buy_price = buy_price is None or int(buy_price or 0) == 0
if missing_buy_price:
    st.warning("⚠️ Buying price missing. Cost will be recorded as 0 unless updated by Admin.")
    confirm_no_cost = st.checkbox("Proceed without buying price")
else:
    confirm_no_cost = True

# ----------------------------
# LOAD SIZES FOR PRODUCT
# ----------------------------
conn = get_db()
sizes_df = pd.read_sql(
    """
    SELECT size, quantity
    FROM product_sizes
    WHERE product_id = ?
    """,
    conn,
    params=(product_id,)
)
conn.close()

if sizes_df.empty:
    st.warning("⚠️ No sizes available for this product. Add sizes before selling.")
    size = None
else:
    size = st.selectbox(
        "Select Size",
        sizes_df["size"].astype(str)
    )

# ----------------------------
# SALE INPUTS
# ----------------------------
quantity = st.number_input(
    "Quantity Sold",
    min_value=1,
    step=1
)

payment_method = st.radio(
    "Payment Method",
    ["Cash", "M-Pesa Paybill"]
)

notes = st.text_area(
    "📝 Sale Notes (optional)",
    placeholder="Any remarks about this sale"
)

# ----------------------------
# SELL ACTION
# ----------------------------
if st.button("💰 SELL"):
    if not confirm_no_cost:
        st.error("❌ Buying price missing. Please ask Admin to update before selling.")
        st.stop()
    if size is None:
        st.error("❌ Cannot sell product without size stock.")
        st.stop()

    conn = get_db()
    cur = conn.cursor()

    # 1️⃣ Check size stock
    cur.execute(
        """
        SELECT quantity
        FROM product_sizes
        WHERE product_id = ? AND size = ?
        """,
        (product_id, size)
    )
    row = cur.fetchone()

    if not row:
        st.error(f"❌ No stock found for size {size}.")
        conn.close()
        st.stop()

    size_stock = int(row[0])

    if quantity > size_stock:
        st.error(f"❌ Only {size_stock} pairs available for size {size}.")
        conn.close()
        st.stop()

    # 2️⃣ Calculate financials
    # 2️⃣ Calculate financials
    revenue = int(quantity * sell_price)
    cost = int((buy_price or 0) * quantity)
    

    # 3️⃣ Deduct size stock
    cur.execute(
        """
        UPDATE product_sizes
        SET quantity = quantity - ?
        WHERE product_id = ? AND size = ?
        """,
        (quantity, product_id, size)
    )

    # 4️⃣ Record sale (WITH SIZE)
    cur.execute(
        """
        INSERT INTO sales
        (product_id, size, quantity, revenue, cost, payment_method, sale_date, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(product_id),
            str(size),
            int(quantity),
            int(revenue),
            int(cost),
            str(payment_method),
            datetime.now().strftime("%Y-%m-%d"),
            notes
        )
    )

    conn.commit()
    conn.close()

    # 5️⃣ Success UI
    st.success("✅ Sale completed successfully!")
    st.write(f"🥿 Product: {selected_product}")
    st.write(f"📏 Size: {size}")
    st.write(f"📦 Quantity: {quantity}")
    st.write(f"💰 Revenue: KES {revenue}")
    st.balloons()
