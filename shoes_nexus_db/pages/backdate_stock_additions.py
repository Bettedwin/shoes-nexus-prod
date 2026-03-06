from db_config import DB_PATH
import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, timedelta
import json
from theme_admin import apply_admin_theme, now_nairobi_str
from ui_feedback import show_success_summary

# ============================================
# DATABASE CONNECTION
# ============================================
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_backdate_approval_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS backdate_approval_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            requested_by TEXT,
            requested_role TEXT,
            approved_by TEXT,
            admin_note TEXT,
            applied_reference_id INTEGER,
            error_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            decided_at DATETIME
        )
        """
    )
    conn.commit()
    conn.close()

# ============================================
# PAGE SETUP
# ============================================
st.set_page_config(page_title="Backdate Stock", layout="wide")
apply_admin_theme(
    "Backdate Stock Additions",
    "Record approved historical stock additions.",
)

if not st.session_state.get("logged_in", False):
    st.warning("Session expired. Please log in again.")
    if st.button("Go to Login", key="backdate_stock_go_login"):
        st.switch_page("app.py")
    st.stop()

# ============================================
# ACCESS CONTROL
# ============================================
if "role" not in st.session_state or st.session_state.role not in ["Admin", "Manager"]:
    st.error("⛔ Access Denied - Admin or Manager role required")
    st.stop()

ensure_backdate_approval_table()

st.info("ℹ️ Use this module to correct or add historical stock")

# ============================================
# STEP 1: DATE SELECTION
# ============================================
st.subheader("Step 1: Select Stock Arrival Date")

stock_date = st.date_input(
    "Stock Arrival Date",
    value=date.today() - timedelta(days=1),
    max_value=date.today() - timedelta(days=1),
    help="Backdate must be before today."
)

st.write(f"📅 Selected date: **{stock_date}**")

# ============================================
# STEP 2: PRODUCT SELECTION
# ============================================
st.subheader("Step 2: Select Product & Size")

conn = get_db()

products = pd.read_sql("""
    SELECT id, brand, model, color, category
    FROM products
    WHERE is_active = 1
    ORDER BY brand, model
""", conn)

if products.empty:
    st.warning("⚠️ No products in inventory")
    conn.close()
    st.stop()

for col in ["brand", "model", "color", "category"]:
    products[col] = products[col].fillna("").astype(str)

brand_options = sorted(products["brand"].dropna().astype(str).unique().tolist())
selected_brand = st.selectbox("Select Brand", brand_options, key="backdate_stock_brand")

models_df = products[products["brand"] == selected_brand].copy()
model_options = sorted(models_df["model"].dropna().astype(str).unique().tolist())
selected_model = st.selectbox("Select Model", model_options, key="backdate_stock_model")

colors_df = models_df[models_df["model"] == selected_model].copy()
color_options = sorted(colors_df["color"].dropna().astype(str).unique().tolist())
selected_color = st.selectbox("Select Color", color_options, key="backdate_stock_color")

selected_row = colors_df[colors_df["color"] == selected_color].iloc[0]
product_id = int(selected_row["id"])
selected_product = f"{selected_brand} {selected_model} ({selected_color})"

# Get existing sizes for this product
sizes_df = pd.read_sql("""
    SELECT size, quantity
    FROM product_sizes
    WHERE product_id = ?
    ORDER BY size
""", conn, params=(product_id,))

product_row = products[products["id"] == product_id].iloc[0]
category = str(product_row.get("category", "")).strip().lower()
if category == "women":
    category_sizes = {str(s) for s in range(35, 42)}
else:
    category_sizes = {str(s) for s in range(40, 46)}
existing_sizes = set(sizes_df["size"].dropna().astype(str).tolist()) if not sizes_df.empty else set()
all_sizes = sorted(existing_sizes.union(category_sizes), key=lambda x: (len(str(x)), str(x)))

size = st.selectbox("Select Size", all_sizes, key="backdate_stock_size")
use_custom_size = st.checkbox("Use custom size (outside listed range)", key="backdate_stock_custom_toggle")
if use_custom_size:
    custom_size = st.text_input("Custom Size", key="backdate_stock_custom_input").strip()
    if custom_size:
        size = custom_size

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
        if stock_date >= date.today():
            st.error("❌ Backdate must be before today.")
            st.stop()
        cur = conn.cursor()

        try:
            if st.session_state.role == "Manager":
                payload = {
                    "product_id": int(product_id),
                    "selected_product": str(selected_product),
                    "size": str(size),
                    "quantity": int(quantity),
                    "stock_date": str(stock_date),
                    "notes": str(notes),
                }
                cur.execute(
                    """
                    INSERT INTO backdate_approval_requests
                    (request_type, payload_json, status, requested_by, requested_role)
                    VALUES (?, ?, 'PENDING', ?, ?)
                    """,
                    (
                        "BACKDATE_STOCK",
                        json.dumps(payload),
                        st.session_state.username,
                        st.session_state.role,
                    ),
                )
                request_id = cur.lastrowid
                cur.execute(
                    """
                    INSERT INTO activity_log
                    (event_type, reference_id, role, username, message)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "BACKDATE_STOCK_REQUEST",
                        request_id,
                        st.session_state.role,
                        st.session_state.username,
                        f"Submitted backdated stock request for admin approval. Effective date: {stock_date}. Product: {selected_product}. Size: {size}. Qty: +{quantity}. Submitted at: {now_nairobi_str()}",
                    ),
                )
                conn.commit()
                show_success_summary(
                    "Request submitted for admin approval.",
                    [
                        ("Request ID", f"#{request_id}"),
                        ("Type", "Backdated stock addition"),
                        ("Product", str(selected_product)),
                        ("Size", str(size)),
                        ("Quantity Added", int(quantity)),
                        ("Effective Date", str(stock_date)),
                    ],
                )
                st.stop()

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
                f"Backdated stock recorded. Effective date: {stock_date}. Product: {selected_product}. Size: {size}. Qty: +{quantity}. Notes: {notes}. Logged at: {now_nairobi_str()}"
            ))

            conn.commit()
            
            show_success_summary(
                "Stock updated successfully.",
                [
                    ("Product", str(selected_product)),
                    ("Size", str(size)),
                    ("Quantity Added", int(quantity)),
                    ("Effective Date", str(stock_date)),
                ],
            )
                        
            # Show new stock level
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
else:
    st.warning("⚠️ Please enter a size")
