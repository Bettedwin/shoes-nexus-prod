from db_config import DB_PATH
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import uuid
import json
from theme_admin import apply_admin_theme, now_nairobi_str
from ui_feedback import show_success_summary

CUSTOMER_SOURCE_OPTIONS = [
    "In-store Walkins",
    "Facebook",
    "Instagram",
    "TikTok",
    "Twitter",
    "Website",
    "Referral/Returning Customer",
    "Other",
]


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def render_theme_notice(message: str) -> None:
    st.markdown(
        (
            "<div style='background:#fff7f8;border:1px solid #f5c2c7;border-left:4px solid #c41224;"
            "border-radius:12px;padding:10px 12px;margin:6px 0 10px 0;color:#141821;font-weight:600;'>"
            f"{message}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def ensure_activity_log():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            reference_id INTEGER,
            role TEXT,
            username TEXT,
            message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_activity_log_nairobi_time
        AFTER INSERT ON activity_log
        FOR EACH ROW
        BEGIN
            UPDATE activity_log
            SET created_at = DATETIME(NEW.created_at, '+3 hours')
            WHERE id = NEW.id;
        END;
        """
    )
    conn.commit()
    conn.close()


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


def ensure_sales_source_column():
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE sales ADD COLUMN source TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def ensure_sales_checkout_columns():
    conn = get_db()
    cur = conn.cursor()
    for ddl in [
        "ALTER TABLE sales ADD COLUMN paid_time TEXT",
        "ALTER TABLE sales ADD COLUMN fulfillment_type TEXT",
        "ALTER TABLE sales ADD COLUMN delivery_option TEXT",
        "ALTER TABLE sales ADD COLUMN delivery_location TEXT",
        "ALTER TABLE sales ADD COLUMN payment_cash_amount REAL DEFAULT 0",
        "ALTER TABLE sales ADD COLUMN payment_mpesa_amount REAL DEFAULT 0",
        "ALTER TABLE sales ADD COLUMN discount_type TEXT",
        "ALTER TABLE sales ADD COLUMN discount_value REAL DEFAULT 0",
        "ALTER TABLE sales ADD COLUMN discount_amount REAL DEFAULT 0",
        "ALTER TABLE sales ADD COLUMN gross_revenue REAL DEFAULT 0",
    ]:
        try:
            cur.execute(ddl)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

def ensure_sales_tracking_columns():
    conn = get_db()
    cur = conn.cursor()
    for ddl in [
        "ALTER TABLE sales ADD COLUMN sale_time TEXT",
        "ALTER TABLE sales ADD COLUMN customer_session_id TEXT",
        "ALTER TABLE sales ADD COLUMN customer_count_unit INTEGER DEFAULT 1",
    ]:
        try:
            cur.execute(ddl)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


def generate_customer_session_id():
    return f"C{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

def render_required_time_paid(mode_key, time_key, help_text="Type an exact time (e.g. 06:42)."):
    mode = st.selectbox(
        "Time Paid",
        ["Select Time", "Set Time"],
        key=mode_key,
    )
    if mode == "Set Time":
        return st.time_input(
            "Choose Time",
            key=time_key,
            step=60,
            help=help_text,
        )
    return None

def reset_backdate_sale_form_state():
    keep = {"backdate_sale_date_v2"}
    for state_key in list(st.session_state.keys()):
        if state_key in keep:
            continue
        if state_key.startswith("backdate2_"):
            st.session_state.pop(state_key, None)
    st.session_state.active_customer_session_id = None
    st.session_state["backdate2_paid_time_mode"] = "Select Time"
    st.session_state["backdate2_broker_paid_time_mode"] = "Select Time"


def get_or_create_brokered_product():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id FROM products
        WHERE category = 'External' AND brand = 'Brokered' AND model = 'Brokered Sale'
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if row:
        conn.close()
        return int(row[0])

    cur.execute(
        """
        INSERT INTO products (category, brand, model, color, buying_price, selling_price, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        ("External", "Brokered", "Brokered Sale", "N/A", 0, 0),
    )
    brokered_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return brokered_id


st.set_page_config(page_title="Backdate Sales", layout="wide")
apply_admin_theme(
    "Backdate Sales",
    "Record approved historical sales entries.",
)

if not st.session_state.get("logged_in", False):
    st.warning("Session expired. Please log in again.")
    if st.button("Go to Login", key="backdate_sales_go_login"):
        st.switch_page("app.py")
    st.stop()

if "role" not in st.session_state or st.session_state.role not in ["Admin", "Manager"]:
    st.error("Access Denied - Admin or Manager role required")
    st.stop()

ensure_sales_source_column()
ensure_sales_checkout_columns()
ensure_sales_tracking_columns()
ensure_activity_log()
ensure_backdate_approval_table()

render_theme_notice("Use this module to enter historical sales data.")

if st.session_state.get("backdate2_flash"):
    flash = st.session_state.get("backdate2_flash_payload", {})
    show_success_summary(
        str(flash.get("title", "Saved successfully.")),
        list(flash.get("rows", [])),
    )
    st.session_state["backdate2_flash"] = False
    st.session_state["backdate2_flash_payload"] = {}

# Exact POS-like layout for backdated sales (active path).
st.markdown(
    "<h2 style='margin:0 0 .5rem 0; color:#0b0b0f; font-weight:800;'>🧾 Shoes Nexus POS</h2>",
    unsafe_allow_html=True,
)
if "active_customer_session_id" not in st.session_state:
    st.session_state.active_customer_session_id = None
session_col1, session_col2 = st.columns([3, 1], gap="small")
with session_col1:
    st.caption(f"Active customer session: {st.session_state.active_customer_session_id or 'None'}")
with session_col2:
    if st.button("Next Customer", key="backdate_next_customer_v2"):
        st.session_state.active_customer_session_id = None
        st.rerun()

backdate_col1, backdate_col2 = st.columns([1.2, 2], gap="small")
with backdate_col1:
    today = date.today()
    latest_backdate = today - timedelta(days=1)
    sale_date = st.date_input(
        "Backdate Date",
        value=latest_backdate,
        max_value=latest_backdate,
        help="Backdate must be before today.",
        key="backdate_sale_date_v2",
    )
with backdate_col2:
    st.caption(f"Selected historical sale date: {sale_date}")

with st.expander("🤝 Brokered Sale (Profit Only)", expanded=False):
    broker_category = st.selectbox("Category", ["Men", "Women", "Accessories", "Other"], key="backdate2_broker_category")
    broker_brand = st.text_input("Brand (e.g. Casio, Timberland)", key="backdate2_broker_brand")
    broker_model = st.text_input("Model / Item", key="backdate2_broker_model")
    broker_color = st.text_input("Color / Variant", key="backdate2_broker_color")
    broker_size = st.text_input("Size (optional, e.g. 38, 40, Free Size)", key="backdate2_broker_size")
    broker_profit = st.number_input("Profit per item (KES)", min_value=0, step=50, key="backdate2_broker_profit")
    broker_qty = st.number_input("Quantity", min_value=1, step=1, key="backdate2_broker_qty")
    broker_total = int(broker_profit) * int(broker_qty)
    st.caption(f"Total profit (KES): {broker_total}")
    broker_payment_mode = st.radio("Payment Mode", ["CASH", "MPESA", "MIXED"], horizontal=True, key="backdate2_broker_payment_mode")
    broker_paid_time = render_required_time_paid(
        "backdate2_broker_paid_time_mode",
        "backdate2_broker_paid_time",
    )
    broker_fulfillment = st.selectbox("Fulfillment", ["In-store Pickup", "Delivery"], key="backdate2_broker_fulfillment")
    broker_delivery_option = ""
    broker_delivery_location = ""
    if broker_fulfillment == "Delivery":
        bd_col1, bd_col2 = st.columns(2)
        with bd_col1:
            broker_delivery_option = st.text_input(
                "Rider / Delivery Option Used",
                key="backdate2_broker_delivery_option",
                placeholder="Rider name, in-house rider, Bolt, Uber, etc.",
            ).strip()
        with bd_col2:
            broker_delivery_location = st.text_input(
                "Delivery Location",
                key="backdate2_broker_delivery_location",
                placeholder="Estate, area, landmark, or town",
            ).strip()
    broker_discount_type = st.selectbox(
        "Discount Type",
        ["None", "Cash Amount", "Percentage"],
        key="backdate2_broker_discount_type",
    )
    broker_discount_value = 0.0
    if broker_discount_type == "Cash Amount":
        broker_discount_value = st.number_input(
            "Discount Amount (KES)",
            min_value=0.0,
            step=50.0,
            key="backdate2_broker_discount_cash",
        )
    elif broker_discount_type == "Percentage":
        broker_discount_value = st.number_input(
            "Discount Percentage (%)",
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            key="backdate2_broker_discount_pct",
        )
    broker_gross = float(int(broker_profit) * int(broker_qty))
    if broker_discount_type == "Cash Amount":
        broker_discount_amount = min(float(broker_discount_value), broker_gross)
    elif broker_discount_type == "Percentage":
        broker_discount_amount = round((broker_gross * float(broker_discount_value)) / 100.0, 2)
    else:
        broker_discount_amount = 0.0
    broker_net = max(broker_gross - broker_discount_amount, 0.0)
    st.caption(f"Net amount payable (KES): {int(broker_net)}")
    broker_cash_amount = 0.0
    broker_mpesa_amount = 0.0
    if broker_payment_mode == "MIXED":
        c_cash, c_mpesa = st.columns(2)
        with c_cash:
            broker_cash_amount = st.number_input(
                "Cash Amount (KES)",
                min_value=0.0,
                step=50.0,
                key="backdate2_broker_cash_amount",
            )
        with c_mpesa:
            broker_mpesa_amount = st.number_input(
                "M-Pesa Amount (KES)",
                min_value=0.0,
                step=50.0,
                key="backdate2_broker_mpesa_amount",
            )
    elif broker_payment_mode == "CASH":
        broker_cash_amount = broker_net
    else:
        broker_mpesa_amount = broker_net
    broker_notes = st.text_area("Notes (optional)", key="backdate2_broker_notes")
    broker_same_customer = st.checkbox(
        "Add brokered line to current customer session",
        key="backdate2_broker_same_customer",
    )

    if st.button("✅ Record Brokered Sale", key="backdate2_record_brokered"):
        if sale_date >= date.today():
            st.error("❌ Backdate must be before today.")
            st.stop()
        if broker_profit <= 0:
            st.error("❌ Profit must be greater than 0.")
            st.stop()
        if not broker_model.strip():
            st.error("❌ Item description is required.")
            st.stop()
        if broker_fulfillment == "Delivery" and not broker_delivery_option:
            st.error("❌ Rider / delivery option is required for delivery orders.")
            st.stop()
        if broker_fulfillment == "Delivery" and not broker_delivery_location:
            st.error("❌ Delivery location is required for delivery orders.")
            st.stop()
        if broker_payment_mode == "MIXED":
            if round(float(broker_cash_amount) + float(broker_mpesa_amount), 2) != round(float(broker_net), 2):
                st.error("❌ Mixed payment totals must equal net amount payable.")
                st.stop()
        if broker_paid_time is None:
            st.error("❌ Please select Time Paid.")
            st.stop()
        revenue = int(broker_net)
        conn = get_db()
        cur = conn.cursor()
        try:
            if broker_same_customer:
                customer_session_id = st.session_state.active_customer_session_id
                if not customer_session_id:
                    st.error("❌ No active customer session. Record a new customer item first.")
                    st.stop()
                customer_count_unit = 0
            else:
                customer_session_id = generate_customer_session_id()
                st.session_state.active_customer_session_id = customer_session_id
                customer_count_unit = 1

            payload = {
                "sale_type": "Brokered Sale (Profit Only)",
                "sale_date": str(sale_date),
                "quantity": int(broker_qty),
                "revenue": int(revenue),
                "cost": 0,
                "payment_method": str(broker_payment_mode),
                "source": "Brokered",
                "broker_category": str(broker_category).strip(),
                "broker_brand": str(broker_brand).strip(),
                "broker_model": str(broker_model).strip(),
                "broker_color": str(broker_color).strip(),
                "broker_size": str(broker_size).strip(),
                "sale_time": datetime.now().strftime("%H:%M:%S"),
                "paid_time": broker_paid_time.strftime("%H:%M:%S"),
                "fulfillment_type": broker_fulfillment,
                "delivery_option": broker_delivery_option if broker_fulfillment == "Delivery" else "",
                "delivery_location": broker_delivery_location if broker_fulfillment == "Delivery" else "",
                "payment_cash_amount": float(broker_cash_amount),
                "payment_mpesa_amount": float(broker_mpesa_amount),
                "discount_type": broker_discount_type,
                "discount_value": float(broker_discount_value),
                "discount_amount": float(broker_discount_amount),
                "gross_revenue": float(broker_gross),
                "customer_session_id": str(customer_session_id),
                "customer_count_unit": int(customer_count_unit),
                "notes": (
                    f"Brokered Sale | {broker_category} | "
                    f"{broker_brand} {broker_model} {broker_color} | "
                    f"Size {str(broker_size).strip() or 'N/A'} | "
                    f"Profit/item KES {int(broker_profit)}. {broker_notes}"
                ).strip(),
            }

            if st.session_state.role == "Manager":
                cur.execute(
                    """
                    INSERT INTO backdate_approval_requests
                    (request_type, payload_json, status, requested_by, requested_role)
                    VALUES (?, ?, 'PENDING', ?, ?)
                    """,
                    ("BACKDATE_SALE", json.dumps(payload), st.session_state.username, st.session_state.role),
                )
                request_id = int(cur.lastrowid)
                cur.execute(
                    """
                    INSERT INTO activity_log
                    (event_type, reference_id, role, username, message)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "BACKDATE_SALE_REQUEST",
                        request_id,
                        st.session_state.role,
                        st.session_state.username,
                        f"Submitted backdated brokered sale request for admin approval. Effective date: {sale_date}. Qty: {broker_qty}. Net revenue: KES {revenue:,}. Submitted at: {now_nairobi_str()}",
                    ),
                )
                conn.commit()
                show_success_summary(
                    "Request submitted for admin approval.",
                    [
                        ("Request ID", f"#{request_id}"),
                        ("Type", "Backdated brokered sale"),
                        ("Effective Date", str(sale_date)),
                    ],
                )
                reset_backdate_sale_form_state()
                conn.close()
                st.rerun()

            brokered_product_id = get_or_create_brokered_product()
            cur.execute(
                """
                INSERT INTO sales
                (product_id, size, quantity, revenue, cost, payment_method, source, sale_date, sale_time, paid_time, fulfillment_type, delivery_option, delivery_location, payment_cash_amount, payment_mpesa_amount, discount_type, discount_value, discount_amount, gross_revenue, customer_session_id, customer_count_unit, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    brokered_product_id,
                    str(broker_size).strip() or "N/A",
                    int(broker_qty),
                    revenue,
                    0,
                    str(broker_payment_mode),
                    "Brokered",
                    str(sale_date),
                    datetime.now().strftime("%H:%M:%S"),
                    broker_paid_time.strftime("%H:%M:%S"),
                    broker_fulfillment,
                    broker_delivery_option if broker_fulfillment == "Delivery" else "",
                    broker_delivery_location if broker_fulfillment == "Delivery" else "",
                    float(broker_cash_amount),
                    float(broker_mpesa_amount),
                    broker_discount_type,
                    float(broker_discount_value),
                    float(broker_discount_amount),
                    float(broker_gross),
                    customer_session_id,
                    int(customer_count_unit),
                    payload["notes"],
                ),
            )
            cur.execute(
                """
                INSERT INTO activity_log
                (event_type, reference_id, role, username, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "BROKERED_SALE",
                    int(brokered_product_id),
                    st.session_state.role if "role" in st.session_state else "Staff",
                    st.session_state.username if "username" in st.session_state else "staff",
                    f"Backdated brokered sale recorded for {sale_date}: {broker_brand} {broker_model} {broker_color} | Size {str(broker_size).strip() or 'N/A'} | Profit/item KES {int(broker_profit)} | Qty {int(broker_qty)}",
                ),
            )
            conn.commit()
            st.session_state["backdate2_flash"] = True
            st.session_state["backdate2_flash_payload"] = {
                "title": "Brokered sale recorded.",
                "rows": [
                    ("Date", str(sale_date)),
                    ("Brand", str(broker_brand)),
                    ("Model", str(broker_model)),
                    ("Color", str(broker_color)),
                    ("Size", str(broker_size).strip() or "N/A"),
                    ("Quantity", int(broker_qty)),
                    ("Net Revenue (KES)", int(revenue)),
                ],
            }
            reset_backdate_sale_form_state()
            st.rerun()
        except Exception as e:
            conn.rollback()
            st.error(f"❌ Error recording brokered sale: {e}")
        finally:
            conn.close()

conn = get_db()
products_df = pd.read_sql(
    """
    SELECT id, brand, model, color, selling_price, buying_price
    FROM products
    WHERE is_active = 1
      AND NOT (
          LOWER(TRIM(COALESCE(category, ''))) = 'external'
          AND LOWER(TRIM(COALESCE(brand, ''))) = 'brokered'
          AND LOWER(TRIM(COALESCE(model, ''))) = 'brokered sale'
      )
    """,
    conn
)
if products_df.empty:
    st.warning("No products available.")
    conn.close()
    st.stop()
for col in ["brand", "model", "color"]:
    products_df[col] = products_df[col].fillna("").astype(str)
search_query = st.text_input("Search item in inventory", placeholder="Type brand, model, or color...", key="backdate2_search_query")
q = (search_query or "").strip().lower()
if q:
    searchable = (
        products_df["brand"].str.lower() + " " +
        products_df["model"].str.lower() + " " +
        products_df["color"].str.lower()
    )
    tokens = [t for t in q.split() if t]
    mask = pd.Series(True, index=products_df.index)
    for token in tokens:
        mask &= searchable.str.contains(token, na=False, regex=False)
    products_df = products_df[mask]
    if products_df.empty:
        st.warning("No products match your search.")
        conn.close()
        st.stop()

if q:
    st.caption(f"Found {len(products_df)} matching product record(s).")

brand_options = sorted(products_df["brand"].dropna().astype(str).unique().tolist())
if not brand_options:
    st.warning("No brands available.")
    conn.close()
    st.stop()
brand_select_options = ["Select brand"] + brand_options
selected_brand = st.selectbox("Select Brand", brand_select_options, key="backdate2_brand")
if selected_brand == "Select brand":
    conn.close()
    st.stop()

models_df = products_df[products_df["brand"] == selected_brand].copy()
model_options = sorted(models_df["model"].dropna().astype(str).unique().tolist())
if not model_options:
    st.warning("No models available for selected brand.")
    conn.close()
    st.stop()
model_select_options = ["Select model"] + model_options
selected_model = st.selectbox("Select Model", model_select_options, key="backdate2_model")
if selected_model == "Select model":
    conn.close()
    st.stop()

colors_df = models_df[models_df["model"] == selected_model].copy()
color_options = sorted(colors_df["color"].dropna().astype(str).unique().tolist())
if not color_options:
    st.warning("No colors available for selected model.")
    conn.close()
    st.stop()
color_select_options = ["Select color"] + color_options
selected_color = st.selectbox("Select Color", color_select_options, key="backdate2_color")
if selected_color == "Select color":
    conn.close()
    st.stop()

product = colors_df[colors_df["color"] == selected_color].iloc[0]
selected_product = f"{selected_brand} {selected_model} ({selected_color})"
product_id = int(product["id"])
sell_price = int(product["selling_price"])
buy_price = product["buying_price"]

sizes_df = pd.read_sql(
"""
SELECT size, quantity
FROM product_sizes
WHERE product_id = ?
ORDER BY size
""",
conn,
params=(product_id,)
)
sizes_df = sizes_df[sizes_df["quantity"] > 0]
if sizes_df.empty:
    render_theme_notice("This product is SOLD OUT.")
    conn.close()
    st.stop()

size_options = ["Select size"] + sizes_df["size"].astype(str).tolist()
size = st.selectbox("Select Size", size_options, key="backdate2_size")
quantity = st.number_input("Quantity", min_value=0, step=1, key="backdate2_quantity")
payment_mode = st.radio("Payment Mode", ["CASH", "MPESA", "MIXED"], horizontal=True, key="backdate2_payment_mode")
paid_time = render_required_time_paid(
    "backdate2_paid_time_mode",
    "backdate2_paid_time",
)
fulfillment_type = st.selectbox("Fulfillment", ["In-store Pickup", "Delivery"], key="backdate2_fulfillment_type")
delivery_option = ""
delivery_location = ""
if fulfillment_type == "Delivery":
    d_col1, d_col2 = st.columns(2)
    with d_col1:
        delivery_option = st.text_input(
            "Rider / Delivery Option Used",
            key="backdate2_delivery_option",
            placeholder="Rider name, in-house rider, Bolt, Uber, etc.",
        ).strip()
    with d_col2:
        delivery_location = st.text_input(
            "Delivery Location",
            key="backdate2_delivery_location",
            placeholder="Estate, area, landmark, or town",
        ).strip()

source = st.selectbox("Customer Source", CUSTOMER_SOURCE_OPTIONS, key="backdate2_source")
discount_type = st.selectbox("Discount Type", ["None", "Cash Amount", "Percentage"], key="backdate2_discount_type")
discount_value = 0.0
if discount_type == "Cash Amount":
    discount_value = st.number_input("Discount Amount (KES)", min_value=0.0, step=50.0, key="backdate2_discount_cash")
elif discount_type == "Percentage":
    discount_value = st.number_input("Discount Percentage (%)", min_value=0.0, max_value=100.0, step=1.0, key="backdate2_discount_pct")
gross_revenue = float(int(quantity) * int(sell_price))
if discount_type == "Cash Amount":
    discount_amount = min(float(discount_value), gross_revenue)
elif discount_type == "Percentage":
    discount_amount = round((gross_revenue * float(discount_value)) / 100.0, 2)
else:
    discount_amount = 0.0
net_revenue = max(gross_revenue - discount_amount, 0.0)
st.caption(f"Net amount payable (KES): {int(net_revenue)}")
cash_amount = 0.0
mpesa_amount = 0.0
if payment_mode == "MIXED":
    c_cash, c_mpesa = st.columns(2)
    with c_cash:
        cash_amount = st.number_input("Cash Amount (KES)", min_value=0.0, step=50.0, key="backdate2_cash_amount")
    with c_mpesa:
        mpesa_amount = st.number_input("M-Pesa Amount (KES)", min_value=0.0, step=50.0, key="backdate2_mpesa_amount")
elif payment_mode == "CASH":
    cash_amount = net_revenue
else:
    mpesa_amount = net_revenue

notes = st.text_area("📝 Sales Notes (optional)", key="backdate2_notes")
same_customer = st.checkbox(
    "Add this sale as another line item for current customer",
    key="backdate2_same_customer_regular",
)
st.caption(f"Selling price: KES {sell_price}")

if st.button("💰 SELL", key="backdate2_sell"):
    if sale_date >= date.today():
        st.error("❌ Backdate must be before today.")
        st.stop()
    error = False
    if size == "Select size":
        st.error("❌ Please select a size.")
        error = True
    if quantity <= 0:
        st.error("❌ Quantity must be greater than 0.")
        error = True
    row = sizes_df[sizes_df["size"].astype(str) == str(size)]
    if row.empty:
        st.error(f"❌ No stock found for size {size}.")
        error = True
    else:
        size_stock = int(row["quantity"].iloc[0])
        if quantity > size_stock:
            st.error(f"❌ Only {size_stock} pairs available for size {size}.")
            error = True
    if not error:
        unit_cost = pd.to_numeric(pd.Series([buy_price]), errors="coerce").iloc[0]
        if pd.isna(unit_cost) or float(unit_cost) <= 0:
            st.error("❌ Buying price is missing for this product. Update buying price before selling.")
            conn.close()
            st.stop()
        if fulfillment_type == "Delivery" and not delivery_option:
            st.error("❌ Rider / delivery option is required for delivery orders.")
            conn.close()
            st.stop()
        if fulfillment_type == "Delivery" and not delivery_location:
            st.error("❌ Delivery location is required for delivery orders.")
            conn.close()
            st.stop()
        if payment_mode == "MIXED":
            if round(float(cash_amount) + float(mpesa_amount), 2) != round(float(net_revenue), 2):
                st.error("❌ Mixed payment totals must equal net amount payable.")
                conn.close()
                st.stop()
        if paid_time is None:
            st.error("❌ Please select Time Paid.")
            conn.close()
            st.stop()

        revenue = int(net_revenue)
        cur = conn.cursor()
        cur.execute("SELECT is_active FROM products WHERE id = ?", (product_id,))
        active_row = cur.fetchone()
        if (not active_row) or int(active_row[0]) != 1:
            st.error("❌ This product is no longer active and cannot be sold.")
            conn.close()
            st.stop()

        if same_customer:
            customer_session_id = st.session_state.active_customer_session_id
            if not customer_session_id:
                conn.rollback()
                conn.close()
                st.error("❌ No active customer session. Record a new customer item first.")
                st.stop()
            customer_count_unit = 0
        else:
            customer_session_id = generate_customer_session_id()
            st.session_state.active_customer_session_id = customer_session_id
            customer_count_unit = 1

        payload = {
            "sale_type": "Regular Sale",
            "sale_date": str(sale_date),
            "product_id": int(product_id),
            "selected_product": str(selected_product),
            "size": str(size),
            "quantity": int(quantity),
            "revenue": int(revenue),
            "cost": int(float(unit_cost) * int(quantity)),
            "payment_method": str(payment_mode),
            "source": str(source),
            "sale_time": datetime.now().strftime("%H:%M:%S"),
            "paid_time": paid_time.strftime("%H:%M:%S"),
            "fulfillment_type": str(fulfillment_type),
            "delivery_option": delivery_option if fulfillment_type == "Delivery" else "",
            "delivery_location": delivery_location if fulfillment_type == "Delivery" else "",
            "payment_cash_amount": float(cash_amount),
            "payment_mpesa_amount": float(mpesa_amount),
            "discount_type": str(discount_type),
            "discount_value": float(discount_value),
            "discount_amount": float(discount_amount),
            "gross_revenue": float(gross_revenue),
            "customer_session_id": str(customer_session_id),
            "customer_count_unit": int(customer_count_unit),
            "notes": str(notes),
        }

        if st.session_state.role == "Manager":
            cur.execute(
                """
                INSERT INTO backdate_approval_requests
                (request_type, payload_json, status, requested_by, requested_role)
                VALUES (?, ?, 'PENDING', ?, ?)
                """,
                ("BACKDATE_SALE", json.dumps(payload), st.session_state.username, st.session_state.role),
            )
            request_id = int(cur.lastrowid)
            cur.execute(
                """
                INSERT INTO activity_log
                (event_type, reference_id, role, username, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "BACKDATE_SALE_REQUEST",
                    request_id,
                    st.session_state.role,
                    st.session_state.username,
                    f"Submitted backdated sale request for admin approval. Effective date: {sale_date}. Qty: {quantity}. Net revenue: KES {revenue:,}. Submitted at: {now_nairobi_str()}",
                ),
            )
            conn.commit()
            show_success_summary(
                "Request submitted for admin approval.",
                [
                    ("Request ID", f"#{request_id}"),
                    ("Type", "Backdated sale"),
                    ("Effective Date", str(sale_date)),
                    ("Quantity", int(quantity)),
                ],
            )
            reset_backdate_sale_form_state()
            conn.close()
            st.rerun()

        cur.execute(
            """
            UPDATE product_sizes
            SET quantity = quantity - ?
            WHERE product_id = ? AND size = ?
            """,
            (quantity, product_id, size)
        )
        cur.execute(
            """
            UPDATE products
            SET stock = (
                SELECT COALESCE(SUM(quantity), 0)
                FROM product_sizes
                WHERE product_id = ?
            )
            WHERE id = ?
            """,
            (product_id, product_id),
        )
        cur.execute(
            """
            INSERT INTO sales
            (product_id, size, quantity, revenue, cost, payment_method, source, sale_date, sale_time, paid_time, fulfillment_type, delivery_option, delivery_location, payment_cash_amount, payment_mpesa_amount, discount_type, discount_value, discount_amount, gross_revenue, customer_session_id, customer_count_unit, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                size,
                quantity,
                revenue,
                int(float(unit_cost) * int(quantity)),
                payment_mode,
                source,
                str(sale_date),
                datetime.now().strftime("%H:%M:%S"),
                paid_time.strftime("%H:%M:%S"),
                fulfillment_type,
                delivery_option if fulfillment_type == "Delivery" else "",
                delivery_location if fulfillment_type == "Delivery" else "",
                float(cash_amount),
                float(mpesa_amount),
                discount_type,
                float(discount_value),
                float(discount_amount),
                float(gross_revenue),
                customer_session_id,
                int(customer_count_unit),
                notes
            )
        )
        sale_id = int(cur.lastrowid)
        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "BACKDATE_SALE",
                sale_id,
                st.session_state.get("role", "Unknown"),
                st.session_state.get("username", "unknown"),
                f"Backdated sale recorded: Product {int(product_id)}, Size {size}, Qty {int(quantity)}, Revenue KES {int(revenue)}, Effective date {sale_date}"
            )
        )
        conn.commit()
        st.session_state["backdate2_flash"] = True
        st.session_state["backdate2_flash_payload"] = {
            "title": "Sale recorded successfully.",
            "rows": [
                ("Product", selected_product),
                ("Size", str(size)),
                ("Quantity", int(quantity)),
                ("Revenue (KES)", int(revenue)),
                ("Backdated To", str(sale_date)),
                ("Sale ID", int(sale_id)),
            ],
        }
        reset_backdate_sale_form_state()
        conn.close()
        st.rerun()

with st.expander("Review a Sale", expanded=False):
    st.caption("Use this when a sale was captured with wrong price, quantity, payment mode, or other issue.")
    render_theme_notice("Open the main POS review flow in the workspace to submit detailed review requests.")

conn.close()
st.stop()
