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

# ----------------------------
# BROKERED SALE (PROFIT ONLY)
# ----------------------------
with st.expander("🤝 Brokered Sale (Profit Only)", expanded=False):
    broker_category = st.selectbox("Category", ["Men", "Women", "Accessories", "Other"], key="broker_category")
    broker_brand = st.text_input("Brand (e.g. Casio, Timberland)", key="broker_brand")
    broker_model = st.text_input("Model / Item", key="broker_model")
    broker_color = st.text_input("Color / Variant", key="broker_color")
    broker_profit = st.number_input("Profit per item (KES)", min_value=0, step=50, key="broker_profit")
    broker_qty = st.number_input("Quantity", min_value=1, step=1, key="broker_qty")
    broker_total = int(broker_profit) * int(broker_qty)
    st.caption(f"Total profit (KES): {broker_total}")
    broker_payment = st.radio("Payment Method", ["Cash", "M-Pesa Paybill"], key="broker_payment")
    broker_notes = st.text_area("Notes (optional)", key="broker_notes")

    if st.button("✅ Record Brokered Sale"):
        if broker_profit <= 0:
            st.error("❌ Profit must be greater than 0.")
            st.stop()
        if not broker_model.strip():
            st.error("❌ Item description is required.")
            st.stop()
        brokered_product_id = get_or_create_brokered_product()
        revenue = int(broker_profit) * int(broker_qty)
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO sales
            (product_id, size, quantity, revenue, cost, payment_method, sale_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                brokered_product_id,
                "N/A",
                int(broker_qty),
                revenue,
                0,
                str(broker_payment),
                datetime.now().strftime("%Y-%m-%d"),
                f"Brokered Sale | {broker_category} | {broker_brand} {broker_model} {broker_color} | Profit/item KES {int(broker_profit)}. {broker_notes}".strip()
            )
        )
        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "BROKERED_SALE",
                brokered_product_id,
                st.session_state.role if "role" in st.session_state else "Staff",
                st.session_state.username if "username" in st.session_state else "staff",
                f"Brokered sale recorded: {broker_brand} {broker_model} {broker_color} | Profit/item KES {int(broker_profit)} | Qty {int(broker_qty)}"
            )
        )
        conn.commit()
        conn.close()
        st.success("✅ Brokered sale recorded")
        st.rerun()

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
