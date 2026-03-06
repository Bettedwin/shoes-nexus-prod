from db_config import DB_PATH
import streamlit as st
import sqlite3
import time
import calendar
import pandas as pd
import json
import uuid
import base64
from datetime import datetime, timezone, timedelta

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from ui_feedback import show_success_summary
from brand_logo import render_brand_logo, get_brand_logo_path

# ----------------------------
# CONFIG
# ----------------------------
SESSION_TIMEOUT = 15 * 60  # 15 minutes

OPERATING_EXPENSE_VOTEHEADS = [
    "Rent",
    "Salaries & Wages",
    "Transport & Fuel",
    "Utilities",
    "Marketing",
    "Repairs & Maintenance",
    "Supplies",
    "Other",
]

# Legacy -> canonical votehead mapping (case-insensitive).
OPERATING_EXPENSE_CATEGORY_MAP = {
    "ads spend": "Marketing",
    "facebook ads": "Marketing",
    "instagram ads": "Marketing",
    "google ads": "Marketing",
    "tiktok ads": "Marketing",
    "marketing": "Marketing",
    "rent": "Rent",
    "salaries": "Salaries & Wages",
    "salary": "Salaries & Wages",
    "salaries & wages": "Salaries & Wages",
    "transport": "Transport & Fuel",
    "transportation": "Transport & Fuel",
    "transport & fuel": "Transport & Fuel",
    "utilities": "Utilities",
    "internet": "Utilities",
    "maintenance": "Repairs & Maintenance",
    "repairs & maintenance": "Repairs & Maintenance",
    "packaging materials": "Supplies",
    "supplies": "Supplies",
    "miscellaneous": "Other",
    "other": "Other",
}


def now_nairobi_str():
    return datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S EAT")
# ============================================
# ----------------------------
# DATABASE CONNECTION
# ----------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# ----------------------------
# BROKERED SALE HELPERS
# ----------------------------
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
#Ensure stock in transit table 
def ensure_stock_in_transit_table():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_in_transit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            size TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_cost REAL NOT NULL,
            expected_date DATE,
            notes TEXT,
            created_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
#ensure net sales view
def ensure_net_sales_view():
    view_sql = """
    CREATE VIEW net_sales AS
    SELECT
        s.id AS sale_id,
        s.product_id,
        s.size,
        (s.quantity - COALESCE(s.returned_quantity, 0)) AS net_quantity,
        CASE
            WHEN s.quantity = 0 THEN 0
            ELSE s.revenue * (s.quantity - COALESCE(s.returned_quantity, 0)) / s.quantity
        END AS net_revenue,
        CASE
            WHEN s.quantity = 0 THEN 0
            ELSE s.cost * (s.quantity - COALESCE(s.returned_quantity, 0)) / s.quantity
        END AS net_cost,
        s.payment_method,
        COALESCE(s.paid_time, '') AS paid_time,
        COALESCE(s.fulfillment_type, '') AS fulfillment_type,
        COALESCE(s.delivery_option, '') AS delivery_option,
        COALESCE(s.payment_cash_amount, 0) AS payment_cash_amount,
        COALESCE(s.payment_mpesa_amount, 0) AS payment_mpesa_amount,
        COALESCE(s.discount_type, 'None') AS discount_type,
        COALESCE(s.discount_value, 0) AS discount_value,
        COALESCE(s.discount_amount, 0) AS discount_amount,
        COALESCE(s.gross_revenue, s.revenue) AS gross_revenue,
        s.source,
        s.notes,
        s.sale_date
    FROM sales s
    WHERE s.return_status != 'FULL';
    """

    last_err = None
    for _ in range(10):
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DROP VIEW IF EXISTS net_sales")
            cur.execute(view_sql)
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            last_err = e
            if "locked" not in str(e).lower():
                raise
            time.sleep(0.2)
        finally:
            if conn is not None:
                conn.close()
    if last_err:
        raise last_err

#Upgrade stock in transit table
def upgrade_stock_in_transit_table():
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("ALTER TABLE stock_in_transit ADD COLUMN expected_date DATE")
    except sqlite3.OperationalError:
        pass

    try:
        cur.execute("ALTER TABLE stock_in_transit ADD COLUMN notes TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

#Ensure opening inventory table
def ensure_opening_inventory_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS opening_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date DATE NOT NULL,
            total_value REAL NOT NULL,
            created_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

#Operating expenses table 
def ensure_operating_expenses_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS operating_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date DATE NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            created_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
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

def ensure_product_public_fields():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(products)")
    columns = [row[1] for row in cur.fetchall()]
    if "image_url" not in columns:
        cur.execute("ALTER TABLE products ADD COLUMN image_url TEXT")
    if "public_brand" not in columns:
        cur.execute("ALTER TABLE products ADD COLUMN public_brand TEXT")
    if "public_title" not in columns:
        cur.execute("ALTER TABLE products ADD COLUMN public_title TEXT")
    if "public_description" not in columns:
        cur.execute("ALTER TABLE products ADD COLUMN public_description TEXT")
    conn.commit()
    conn.close()

def ensure_home_expenses_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS home_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date DATE NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

#return/exchange activity log
# ----------------------------
# ACTIVITY LOG (AUDIT TRAIL)
# ----------------------------
def ensure_activity_log():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            reference_id INTEGER,
            role TEXT,
            username TEXT,
            message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
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

def _norm_text(value):
    return str(value or "").strip().lower()

def ensure_style_catalog_tables():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS styles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT NOT NULL,
            model TEXT NOT NULL,
            brand_norm TEXT NOT NULL,
            model_norm TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(brand_norm, model_norm)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS style_colors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            style_id INTEGER NOT NULL,
            color TEXT NOT NULL,
            color_norm TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(style_id, color_norm)
        )
        """
    )
    for ddl in [
        "ALTER TABLE products ADD COLUMN style_id INTEGER",
        "ALTER TABLE products ADD COLUMN style_color_id INTEGER",
        "ALTER TABLE sales ADD COLUMN style_id INTEGER",
        "ALTER TABLE sales ADD COLUMN style_color_id INTEGER",
    ]:
        try:
            cur.execute(ddl)
        except sqlite3.OperationalError:
            pass
    cur.execute("CREATE INDEX IF NOT EXISTS idx_products_style_id ON products(style_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_products_style_color_id ON products(style_color_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_style_id ON sales(style_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_style_color_id ON sales(style_color_id)")
    conn.commit()
    conn.close()

def backfill_style_catalog(cutover_date="2026-03-01"):
    conn = get_db()
    cur = conn.cursor()
    products_df = pd.read_sql(
        """
        SELECT id, COALESCE(brand, '') AS brand, COALESCE(model, '') AS model, COALESCE(color, '') AS color
        FROM products
        WHERE COALESCE(is_active, 1) = 1
          AND NOT (
              LOWER(TRIM(COALESCE(category, ''))) = 'external'
              AND LOWER(TRIM(COALESCE(brand, ''))) = 'brokered'
              AND LOWER(TRIM(COALESCE(model, ''))) = 'brokered sale'
          )
        """,
        conn,
    )
    if products_df.empty:
        conn.close()
        return

    # 1) Upsert styles and colors.
    style_cache = {}
    style_color_cache = {}
    for _, row in products_df.iterrows():
        brand = str(row["brand"]).strip()
        model = str(row["model"]).strip()
        color = str(row["color"]).strip() or "Unspecified"
        bnorm = _norm_text(brand)
        mnorm = _norm_text(model)
        cnorm = _norm_text(color)
        if not bnorm or not mnorm:
            continue
        cur.execute(
            """
            INSERT OR IGNORE INTO styles (brand, model, brand_norm, model_norm)
            VALUES (?, ?, ?, ?)
            """,
            (brand, model, bnorm, mnorm),
        )
        cur.execute("SELECT id FROM styles WHERE brand_norm = ? AND model_norm = ?", (bnorm, mnorm))
        style_id = int(cur.fetchone()[0])
        style_cache[(bnorm, mnorm)] = style_id

        cur.execute(
            """
            INSERT OR IGNORE INTO style_colors (style_id, color, color_norm)
            VALUES (?, ?, ?)
            """,
            (style_id, color, cnorm),
        )
        cur.execute("SELECT id FROM style_colors WHERE style_id = ? AND color_norm = ?", (style_id, cnorm))
        style_color_id = int(cur.fetchone()[0])
        style_color_cache[(style_id, cnorm)] = style_color_id

        cur.execute(
            """
            UPDATE products
            SET style_id = ?, style_color_id = ?
            WHERE id = ?
            """,
            (style_id, style_color_id, int(row["id"])),
        )

    # 2) Backfill sales style refs from mapped product rows (cutover period).
    cur.execute(
        """
        UPDATE sales
        SET style_id = (SELECT p.style_id FROM products p WHERE p.id = sales.product_id),
            style_color_id = (SELECT p.style_color_id FROM products p WHERE p.id = sales.product_id)
        WHERE date(sale_date) >= date(?)
          AND product_id IS NOT NULL
          AND (
              style_id IS NULL
              OR style_color_id IS NULL
          )
        """,
        (str(cutover_date),),
    )
    conn.commit()
    conn.close()

def ensure_monthly_stock_takes_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS monthly_stock_takes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_key TEXT NOT NULL,
            checkpoint_type TEXT NOT NULL,
            due_date DATE NOT NULL,
            completed_at DATETIME,
            total_products INTEGER,
            total_units INTEGER,
            total_value REAL,
            completed_by TEXT,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(month_key, checkpoint_type)
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_monthly_stock_takes_month_due "
        "ON monthly_stock_takes(month_key, due_date)"
    )
    conn.commit()
    conn.close()

def month_schedule_dates(month_key):
    year, month = [int(x) for x in str(month_key).split("-")]
    start_dt = pd.Timestamp(year=year, month=month, day=1)
    end_day = calendar.monthrange(year, month)[1]
    end_dt = pd.Timestamp(year=year, month=month, day=end_day)
    return {
        "OPENING": start_dt.strftime("%Y-%m-%d"),
        "AUDIT_1": (start_dt + pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
        "AUDIT_2": (start_dt + pd.Timedelta(days=14)).strftime("%Y-%m-%d"),
        "CLOSING": end_dt.strftime("%Y-%m-%d"),
    }

def ensure_month_schedule_rows(conn, month_key):
    schedule = month_schedule_dates(month_key)
    cur = conn.cursor()
    for checkpoint_type, due_date in schedule.items():
        cur.execute(
            """
            INSERT OR IGNORE INTO monthly_stock_takes
            (month_key, checkpoint_type, due_date)
            VALUES (?, ?, ?)
            """,
            (str(month_key), str(checkpoint_type), str(due_date)),
        )
    conn.commit()

def get_live_inventory_totals(conn):
    df = pd.read_sql(
        """
        SELECT
            COALESCE(p.id, 0) AS product_id,
            COALESCE(ps.quantity, 0) AS quantity,
            COALESCE(p.buying_price, 0) AS buying_price
        FROM products p
        LEFT JOIN product_sizes ps ON ps.product_id = p.id
        WHERE COALESCE(p.is_active, 0) = 1
          AND NOT (
              LOWER(TRIM(COALESCE(p.category, ''))) = 'external'
              AND LOWER(TRIM(COALESCE(p.brand, ''))) = 'brokered'
              AND LOWER(TRIM(COALESCE(p.model, ''))) = 'brokered sale'
          )
        """,
        conn,
    )
    if df.empty:
        return {"total_products": 0, "total_units": 0, "total_value": 0.0}
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["buying_price"] = pd.to_numeric(df["buying_price"], errors="coerce").fillna(0)
    df = df[df["quantity"] > 0]
    if df.empty:
        return {"total_products": 0, "total_units": 0, "total_value": 0.0}
    return {
        "total_products": int(df["product_id"].nunique()),
        "total_units": int(df["quantity"].sum()),
        "total_value": float((df["quantity"] * df["buying_price"]).sum()),
    }

def ensure_stock_take_submission_tables():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_take_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_key TEXT,
            checkpoint_type TEXT,
            stock_take_type TEXT NOT NULL,
            stock_take_date DATE NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            submitted_by TEXT,
            submitted_role TEXT,
            approved_by TEXT,
            approved_at DATETIME,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_take_submission_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            size TEXT NOT NULL,
            counted_qty INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_stock_take_submissions_status_created "
        "ON stock_take_submissions(status, created_at)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_stock_take_lines_submission "
        "ON stock_take_submission_lines(submission_id)"
    )
    conn.commit()
    conn.close()

def _stock_take_order():
    return ["OPENING", "AUDIT_1", "AUDIT_2", "CLOSING"]

def _started_checkpoints_for_date(month_key, ref_date=None):
    ref = pd.Timestamp.today().normalize() if ref_date is None else pd.Timestamp(ref_date).normalize()
    schedule = month_schedule_dates(month_key)
    started = ["OPENING"]
    if ref >= pd.Timestamp(schedule["AUDIT_1"]):
        started.append("AUDIT_1")
    if ref >= pd.Timestamp(schedule["AUDIT_2"]):
        started.append("AUDIT_2")
    if ref >= pd.Timestamp(schedule["CLOSING"]):
        started.append("CLOSING")
    return started

def get_required_checkpoint(conn, month_key, ref_date=None):
    ensure_month_schedule_rows(conn, month_key)
    df = pd.read_sql(
        """
        SELECT checkpoint_type, due_date, completed_at
        FROM monthly_stock_takes
        WHERE month_key = ?
        ORDER BY due_date ASC
        """,
        conn,
        params=(month_key,),
    )
    if df.empty:
        return None, df
    started = set(_started_checkpoints_for_date(month_key, ref_date))
    done = {
        str(row["checkpoint_type"]): bool(pd.notna(row["completed_at"]) and str(row["completed_at"]).strip())
        for _, row in df.iterrows()
    }
    for cp in _stock_take_order():
        if cp in started and not done.get(cp, False):
            return cp, df
    return None, df

def reset_mistaken_bulk_stock_take_completions():
    month_key = pd.Timestamp.today().strftime("%Y-%m")
    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT checkpoint_type, completed_at, total_products, total_units, total_value, COALESCE(completed_by, '')
        FROM monthly_stock_takes
        WHERE month_key = ?
          AND checkpoint_type IN ('OPENING', 'AUDIT_1', 'AUDIT_2', 'CLOSING')
        ORDER BY checkpoint_type
        """,
        (month_key,),
    ).fetchall()
    if len(rows) != 4:
        conn.close()
        return
    completed_at_vals = [str(r[1] or "") for r in rows]
    if any(v.strip() == "" for v in completed_at_vals):
        conn.close()
        return
    if len(set(completed_at_vals)) != 1:
        conn.close()
        return
    totals_products = {int(r[2] or 0) for r in rows}
    totals_units = {int(r[3] or 0) for r in rows}
    totals_value = {float(r[4] or 0.0) for r in rows}
    if not (len(totals_products) == 1 and len(totals_units) == 1 and len(totals_value) == 1):
        conn.close()
        return

    cur.execute(
        """
        UPDATE monthly_stock_takes
        SET completed_at = NULL,
            total_products = NULL,
            total_units = NULL,
            total_value = NULL,
            completed_by = NULL
        WHERE month_key = ?
          AND checkpoint_type IN ('OPENING', 'AUDIT_1', 'AUDIT_2', 'CLOSING')
        """,
        (month_key,),
    )
    if int(cur.rowcount or 0) > 0:
        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, NULL, ?, ?, ?)
            """,
            (
                "STOCK_TAKE_COMPLETION_RESET",
                "System",
                "system",
                f"Reset mistaken one-click mandatory stock take completions for {month_key}.",
            ),
        )
    conn.commit()
    conn.close()

def ensure_returns_refund_columns():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS returns_exchanges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            type TEXT,
            size TEXT,
            quantity INTEGER,
            amount REAL DEFAULT 0,
            notes TEXT,
            initiated_by TEXT,
            status TEXT DEFAULT 'PENDING',
            approved_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    for ddl in [
        "ALTER TABLE returns_exchanges ADD COLUMN refund_amount REAL DEFAULT 0",
        "ALTER TABLE returns_exchanges ADD COLUMN refund_method TEXT",
        "ALTER TABLE returns_exchanges ADD COLUMN exchange_mode TEXT",
        "ALTER TABLE returns_exchanges ADD COLUMN exchange_payload TEXT",
        "ALTER TABLE returns_exchanges ADD COLUMN settlement_direction TEXT",
        "ALTER TABLE returns_exchanges ADD COLUMN settlement_amount REAL DEFAULT 0",
        "ALTER TABLE returns_exchanges ADD COLUMN settlement_method TEXT",
    ]:
        try:
            cur.execute(ddl)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

def ensure_stock_cost_layers_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_cost_layers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            size TEXT NOT NULL,
            remaining_qty INTEGER NOT NULL,
            unit_cost REAL NOT NULL,
            source TEXT,
            reference_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_stock_cost_layers_product_size "
        "ON stock_cost_layers(product_id, size, created_at)"
    )
    conn.commit()
    conn.close()

def bootstrap_stock_cost_layers():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO stock_cost_layers (product_id, size, remaining_qty, unit_cost, source)
        SELECT
            ps.product_id,
            ps.size,
            CAST(ps.quantity AS INTEGER),
            CAST(COALESCE(p.buying_price, 0) AS REAL),
            'BOOTSTRAP'
        FROM product_sizes ps
        JOIN products p ON p.id = ps.product_id
        WHERE COALESCE(ps.quantity, 0) > 0
          AND COALESCE(p.buying_price, 0) > 0
          AND NOT EXISTS (
              SELECT 1
              FROM stock_cost_layers scl
              WHERE scl.product_id = ps.product_id
                AND scl.size = ps.size
                AND COALESCE(scl.remaining_qty, 0) > 0
          )
        """
    )
    conn.commit()
    conn.close()

def generate_customer_session_id():
    return f"C{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

def consume_stock_cost_layers(cur, product_id, size, quantity, fallback_unit_cost):
    remaining = int(quantity)
    total_cost = 0
    cur.execute(
        """
        SELECT id, remaining_qty, unit_cost
        FROM stock_cost_layers
        WHERE product_id = ? AND size = ? AND remaining_qty > 0
        ORDER BY id ASC
        """,
        (int(product_id), str(size)),
    )
    for layer_id, layer_qty, unit_cost in cur.fetchall():
        if remaining <= 0:
            break
        take_qty = min(int(layer_qty or 0), remaining)
        if take_qty <= 0:
            continue
        total_cost += int(take_qty * float(unit_cost or 0))
        cur.execute(
            "UPDATE stock_cost_layers SET remaining_qty = remaining_qty - ? WHERE id = ?",
            (int(take_qty), int(layer_id)),
        )
        remaining -= int(take_qty)

    fallback = float(fallback_unit_cost or 0)
    if remaining > 0 and fallback > 0:
        total_cost += int(remaining * fallback)
        remaining = 0

    return int(total_cost), int(remaining)

def ensure_backdate_approval_requests_table():
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
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_backdate_approval_status_created "
        "ON backdate_approval_requests(status, created_at)"
    )
    conn.commit()
    conn.close()

def ensure_sale_review_requests_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sale_review_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            issue_type TEXT NOT NULL,
            expected_value TEXT,
            notes TEXT,
            requested_by TEXT,
            requested_role TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            admin_note TEXT,
            resolved_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_sale_review_status_created "
        "ON sale_review_requests(status, created_at)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_sale_review_sale_id "
        "ON sale_review_requests(sale_id)"
    )
    conn.commit()
    conn.close()

def ensure_product_stock_column():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(products)")
    columns = [row[1] for row in cur.fetchall()]
    if "stock" not in columns:
        cur.execute("ALTER TABLE products ADD COLUMN stock INTEGER DEFAULT 0")
    conn.commit()
    conn.close()

def ensure_db_indexes():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_sale_date ON sales(sale_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_product_id ON sales(product_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_return_status ON sales(return_status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_product_sizes_product_size ON product_sizes(product_id, size)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_activity_log_created_at ON activity_log(created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_activity_log_event_type ON activity_log(event_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_operating_expenses_date ON operating_expenses(expense_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_home_expenses_date ON home_expenses(expense_date)")
    conn.commit()
    conn.close()

def normalize_operating_expense_categories():
    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT id, category FROM operating_expenses"
    ).fetchall()

    updates = []
    for expense_id, raw_category in rows:
        current = str(raw_category or "").strip()
        mapped = OPERATING_EXPENSE_CATEGORY_MAP.get(current.lower(), None)
        if mapped and mapped != current:
            updates.append((mapped, int(expense_id), current))

    for mapped, expense_id, _old in updates:
        cur.execute(
            "UPDATE operating_expenses SET category = ? WHERE id = ?",
            (mapped, int(expense_id)),
        )

    if updates:
        by_target = {}
        for mapped, _expense_id, old in updates:
            by_target.setdefault(mapped, set()).add(old)
        summary = "; ".join(
            f"{target} <= {', '.join(sorted(old_set))}"
            for target, old_set in sorted(by_target.items())
        )
        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "OPERATING_EXPENSE_CATEGORY_NORMALIZED",
                0,
                "System",
                "system",
                f"Normalized {len(updates)} operating expense categories. {summary}",
            ),
        )

    conn.commit()
    conn.close()
    return len(updates)

def sync_all_product_stock():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE products
        SET stock = COALESCE((
            SELECT SUM(ps.quantity)
            FROM product_sizes ps
            WHERE ps.product_id = products.id
        ), 0)
        """
    )
    updated = cur.rowcount
    conn.commit()
    conn.close()
    return int(updated or 0)

def backfill_missing_expense_logs():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO activity_log (event_type, reference_id, role, username, message)
        SELECT
            'OPERATING_EXPENSE',
            oe.id,
            'Admin',
            COALESCE(NULLIF(TRIM(oe.created_by), ''), 'admin'),
            'Operating expense: ' || COALESCE(oe.category, 'Other') || ' - KES ' || CAST(COALESCE(oe.amount, 0) AS INTEGER)
        FROM operating_expenses oe
        LEFT JOIN activity_log al
          ON al.event_type = 'OPERATING_EXPENSE'
         AND al.reference_id = oe.id
        WHERE al.id IS NULL
        """
    )
    operating_inserted = int(cur.rowcount or 0)

    cur.execute(
        """
        INSERT INTO activity_log (event_type, reference_id, role, username, message)
        SELECT
            'HOME_EXPENSE',
            he.id,
            'Admin',
            COALESCE(NULLIF(TRIM(he.created_by), ''), 'admin'),
            'Home expense: ' || COALESCE(he.category, 'Other') || ' - KES ' || CAST(COALESCE(he.amount, 0) AS INTEGER)
        FROM home_expenses he
        LEFT JOIN activity_log al
          ON al.event_type = 'HOME_EXPENSE'
         AND al.reference_id = he.id
        WHERE al.id IS NULL
        """
    )
    home_inserted = int(cur.rowcount or 0)

    conn.commit()
    conn.close()
    return operating_inserted, home_inserted

def count_integrity_issues():
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*)
        FROM products p
        WHERE COALESCE(p.stock, 0) != COALESCE((
            SELECT SUM(ps.quantity)
            FROM product_sizes ps
            WHERE ps.product_id = p.id
        ), 0)
        """
    )
    stock_mismatch = int(cur.fetchone()[0] or 0)

    cur.execute(
        """
        SELECT COUNT(*)
        FROM product_sizes
        WHERE COALESCE(quantity, 0) < 0
        """
    )
    negative_size_rows = int(cur.fetchone()[0] or 0)

    cur.execute(
        """
        SELECT COUNT(*)
        FROM sales s
        LEFT JOIN products p ON p.id = s.product_id
        WHERE COALESCE(s.cost, 0) = 0
          AND COALESCE(s.quantity, 0) > 0
          AND COALESCE(s.revenue, 0) > 0
          AND COALESCE(s.notes, '') NOT LIKE '%Brokered Sale%'
        """
    )
    zero_cost_regular = int(cur.fetchone()[0] or 0)

    cur.execute(
        """
        SELECT COUNT(*)
        FROM operating_expenses oe
        LEFT JOIN activity_log al
          ON al.event_type = 'OPERATING_EXPENSE'
         AND al.reference_id = oe.id
        WHERE al.id IS NULL
        """
    )
    missing_operating_logs = int(cur.fetchone()[0] or 0)

    cur.execute(
        """
        SELECT COUNT(*)
        FROM home_expenses he
        LEFT JOIN activity_log al
          ON al.event_type = 'HOME_EXPENSE'
         AND al.reference_id = he.id
        WHERE al.id IS NULL
        """
    )
    missing_home_logs = int(cur.fetchone()[0] or 0)

    conn.close()
    return {
        "stock_mismatch": stock_mismatch,
        "negative_size_rows": negative_size_rows,
        "zero_cost_regular": zero_cost_regular,
        "missing_operating_logs": missing_operating_logs,
        "missing_home_logs": missing_home_logs,
    }

def backfill_fixable_zero_cost_sales():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE sales
        SET cost = CAST((
            SELECT COALESCE(p.buying_price, 0) * sales.quantity
            FROM products p
            WHERE p.id = sales.product_id
        ) AS INTEGER)
        WHERE COALESCE(cost, 0) = 0
          AND COALESCE(quantity, 0) > 0
          AND COALESCE(revenue, 0) > 0
          AND COALESCE(notes, '') NOT LIKE '%Brokered Sale%'
          AND EXISTS (
              SELECT 1
              FROM products p
              WHERE p.id = sales.product_id
                AND COALESCE(p.buying_price, 0) > 0
          )
        """
    )
    updated = int(cur.rowcount or 0)
    conn.commit()
    conn.close()
    return updated

# ----------------------------
# SESSION MANAGEMENT
# ----------------------------
def init_session():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "role" not in st.session_state:
        st.session_state.role = None
    if "username" not in st.session_state:
        st.session_state.username = None
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = time.time()

def update_activity():
    st.session_state.last_activity = time.time()

def auto_logout():
    if time.time() - st.session_state.last_activity > SESSION_TIMEOUT:
        st.session_state.clear()
        st.session_state.session_expired_notice = True
        st.rerun()

# ----------------------------
# AUTHENTICATION
# ----------------------------
from security import verify_password, hash_password


def ensure_staff_security_columns():
    conn = get_db()
    cur = conn.cursor()
    for ddl in [
        "ALTER TABLE staff ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE staff ADD COLUMN must_change_password INTEGER DEFAULT 0",
        "ALTER TABLE staff ADD COLUMN password_changed_at DATETIME",
    ]:
        try:
            cur.execute(ddl)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

def get_today_snapshot():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            COALESCE(SUM(revenue), 0),
            COALESCE(SUM(cost), 0),
            COALESCE(SUM(quantity), 0),
            COUNT(*),
            COALESCE(SUM(COALESCE(customer_count_unit, 1)), 0)
        FROM sales
        WHERE date(sale_date) = date('now')
        """
    )
    revenue, cost, units, tx_count, customer_count = cur.fetchone()

    cur.execute(
        """
        SELECT substr(COALESCE(sale_time, ''), 1, 2) AS sale_hour, COUNT(*) AS cnt
        FROM sales
        WHERE date(sale_date) = date('now')
          AND COALESCE(sale_time, '') != ''
        GROUP BY substr(COALESCE(sale_time, ''), 1, 2)
        ORDER BY cnt DESC, sale_hour ASC
        LIMIT 1
        """
    )
    peak_row = cur.fetchone()
    peak_hour = f"{peak_row[0]}:00" if peak_row and peak_row[0] else "N/A"

    cur.execute("SELECT COUNT(*) FROM products WHERE is_active = 1")
    active_products = int(cur.fetchone()[0] or 0)

    cur.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT p.id
            FROM products p
            LEFT JOIN product_sizes ps ON ps.product_id = p.id
            WHERE p.is_active = 1
            GROUP BY p.id
            HAVING COALESCE(SUM(ps.quantity), 0) <= 3
        )
        """
    )
    low_stock_count = int(cur.fetchone()[0] or 0)

    conn.close()
    return {
        "revenue": int(revenue or 0),
        "cost": int(cost or 0),
        "profit": int((revenue or 0) - (cost or 0)),
        "units": int(units or 0),
        "tx_count": int(tx_count or 0),
        "customer_count": int(customer_count or 0),
        "peak_hour": peak_hour,
        "active_products": active_products,
        "low_stock_count": low_stock_count,
    }

def render_page_intro(title, subtitle):
    logo_markup = ""
    try:
        logo_path = get_brand_logo_path()
        if logo_path:
            with open(logo_path, "rb") as f:
                logo_b64 = base64.b64encode(f.read()).decode("ascii")
            logo_markup = (
                "<div class='sn-hero-logo'>"
                f"<img src='data:image/png;base64,{logo_b64}' alt='Shoes Nexus Logo'/>"
                "</div>"
            )
    except Exception:
        logo_markup = ""

    st.markdown(
        f"""
        <div class="sn-page-hero">
            <div class="sn-hero-head">
                <h1>{title}</h1>
                {logo_markup}
            </div>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return

def render_kpi_row(snapshot, role_label):
    st.markdown(
        f"""
        <div class="sn-kpi-row">
            <div class="sn-kpi-card">
                <div class="sn-kpi-label">Today Revenue</div>
                <div class="sn-kpi-value">KES {snapshot['revenue']:,}</div>
                <div class="sn-kpi-note">Role: {role_label}</div>
            </div>
            <div class="sn-kpi-card">
                <div class="sn-kpi-label">Today Profit</div>
                <div class="sn-kpi-value">KES {snapshot['profit']:,}</div>
                <div class="sn-kpi-note">From {snapshot['tx_count']} transactions</div>
            </div>
            <div class="sn-kpi-card">
                <div class="sn-kpi-label">Units Sold</div>
                <div class="sn-kpi-value">{snapshot['units']}</div>
                <div class="sn-kpi-note">Across all channels</div>
            </div>
            <div class="sn-kpi-card">
                <div class="sn-kpi-label">Inventory</div>
                <div class="sn-kpi-value">{snapshot['active_products']}</div>
                <div class="sn-kpi-note">{snapshot['low_stock_count']} low stock | {snapshot['customer_count']} customers | Peak {snapshot['peak_hour']}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_section_hint(title, description):
    st.markdown(
        f"""
        <div class="sn-section-hint">
            <div class="sn-section-hint-title">{title}</div>
            <div class="sn-section-hint-text">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_theme_notice(message):
    st.markdown(
        f"""
        <div style="
            border:1px solid #f5c2c7;
            border-left:4px solid #c41224;
            border-radius:12px;
            background:#fff7f8;
            color:#1a1d25;
            padding:0.75rem 0.9rem;
            margin:0.4rem 0 0.6rem 0;
            font-weight:600;
        ">
            {message}
        </div>
        """,
        unsafe_allow_html=True,
    )

def get_sidebar_actions(role):
    if role == "Admin":
        return [
            ("Workspace Sections", [
                ("POS and Sales", "__admin_section__POS and Sales"),
                ("Inventory", "__admin_section__Inventory"),
                ("Stock Operations", "__admin_section__Stock Operations"),
                ("Analytics", "__admin_section__Analytics"),
                ("Finance", "__admin_section__Finance"),
                ("Returns", "__admin_section__Returns"),
                ("Audit and Admin", "__admin_section__Audit and Admin"),
            ]),
            ("Operations", [
                ("Dashboard", "pages/dashboard.py"),
                ("Manage Users", "pages/register_user.py"),
                ("Initial Stock Setup", "pages/initial_stock_setup.py"),
            ]),
            ("History Tools", [
                ("Backdate Sales", "pages/backdate_sales.py"),
                ("Backdate Expenses", "pages/backdate_expenses.py"),
                ("Backdate Stock", "pages/backdate_stock_additions.py"),
            ]),
            ("Support", [
                ("Returns and Exchanges", "pages/returns.py"),
                ("Monthly Report", "pages/monthly_report.py"),
                ("Stock Take", "pages/stock_take.py"),
            ]),
            ("Private", [
                ("Home Expenses", "pages/home_expenses.py"),
            ]),
        ]
    if role == "Manager":
        return [
            ("Workspace Sections", [
                ("POS and Sales", "__manager_section__POS and Sales"),
                ("Inventory", "__manager_section__Inventory"),
                ("Stock Operations", "__manager_section__Stock Operations"),
                ("Returns Desk", "__manager_section__Returns Desk"),
                ("History Tools", "__manager_section__History Tools"),
            ]),
            ("Tools", [
                ("Stock Take", "pages/stock_take.py"),
            ]),
        ]
    return [
        ("Workspace Sections", [
            ("POS and Sales", "__cashier_section__POS and Sales"),
            ("Inventory", "__cashier_section__Inventory"),
            ("Returns and Exchanges", "__cashier_section__Returns and Exchanges"),
        ]),
        ("Tools", [
            ("Stock Take", "pages/stock_take.py"),
        ]),
    ]

def render_sidebar_navigation(role):
    for group_name, actions in get_sidebar_actions(role):
        st.markdown(f"<div class='sn-nav-group'>{group_name}</div>", unsafe_allow_html=True)
        for label, target_page in actions:
            if st.button(label, key=f"nav_{role}_{label}"):
                if isinstance(target_page, str) and target_page.startswith("__manager_section__"):
                    st.session_state.manager_section = target_page.replace("__manager_section__", "", 1)
                    st.rerun()
                    continue
                if isinstance(target_page, str) and target_page.startswith("__admin_section__"):
                    st.session_state.admin_section = target_page.replace("__admin_section__", "", 1)
                    st.rerun()
                    continue
                if isinstance(target_page, str) and target_page.startswith("__cashier_section__"):
                    st.session_state.cashier_section = target_page.replace("__cashier_section__", "", 1)
                    st.rerun()
                    continue
                st.switch_page(target_page)

def login_screen():
    if st.session_state.get("pending_password_change"):
        st.markdown(
            """
            <div class="sn-auth-hero sn-page-hero">
                <h1>Password Update Required</h1>
                <p>Your password was reset by admin. Set a new password to continue.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _, auth_col, _ = st.columns([1.5, 6, 1.5], gap="small")
        with auth_col:
            new_pw = st.text_input("New Password", type="password", key="force_new_password")
            confirm_pw = st.text_input("Confirm New Password", type="password", key="force_confirm_password")
            submit_pw = st.button("Update Password", type="primary", key="force_update_password_submit", use_container_width=True)

        if submit_pw:
            if len(new_pw or "") < 6:
                st.error("Password must be at least 6 characters.")
                return
            if new_pw != confirm_pw:
                st.error("Passwords do not match.")
                return
            user_id = int(st.session_state.get("pending_user_id") or 0)
            if user_id <= 0:
                st.error("Password update session is invalid. Please sign in again.")
                st.session_state.pop("pending_password_change", None)
                st.session_state.pop("pending_user_id", None)
                st.session_state.pop("pending_username", None)
                st.rerun()
                return

            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE staff
                SET password_hash = ?, must_change_password = 0, password_changed_at = DATETIME('now')
                WHERE id = ?
                """,
                (hash_password(new_pw), user_id),
            )
            cur.execute(
                """
                INSERT INTO activity_log (event_type, reference_id, role, username, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "USER_PASSWORD_CHANGED",
                    user_id,
                    "Staff",
                    str(st.session_state.get("pending_username", "")),
                    "User completed forced password change at login.",
                ),
            )
            conn.commit()
            conn.close()

            st.session_state.logged_in = True
            st.session_state.username = st.session_state.get("pending_username")
            st.session_state.role = st.session_state.get("pending_role")
            st.session_state.pop("pending_password_change", None)
            st.session_state.pop("pending_user_id", None)
            st.session_state.pop("pending_username", None)
            st.session_state.pop("pending_role", None)
            update_activity()
            show_success_summary("Password updated successfully.", [("Status", "Access restored")])
            st.rerun()
        return

    logo_markup = ""
    try:
        logo_path = get_brand_logo_path()
        if logo_path:
            with open(logo_path, "rb") as f:
                logo_b64 = base64.b64encode(f.read()).decode("ascii")
            logo_markup = (
                "<div class='sn-auth-hero-logo'>"
                f"<img src='data:image/png;base64,{logo_b64}' alt='Shoes Nexus Logo'/>"
                "</div>"
            )
    except Exception:
        logo_markup = ""

    _, auth_col, _ = st.columns([1.2, 7.6, 1.2], gap="small")
    with auth_col:
        st.markdown(
            f"""
            <div class="sn-auth-hero sn-page-hero">
                <div class="sn-auth-title-row">
                    <h1>Shoes Nexus POS</h1>
                    {logo_markup}
                </div>
                <p>Sign in to continue with sales, inventory, and reports.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    if st.session_state.pop("session_expired_notice", False):
        st.warning("Session expired. Please log in again.")
    with auth_col:
        username = st.text_input("Username", placeholder="Enter your staff username", key="login_username")
        password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password")
        login_clicked = st.button("Sign In", type="primary", key="login_submit")

    if login_clicked:
        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT id, password_hash, role, COALESCE(is_active, 1), COALESCE(must_change_password, 0) FROM staff WHERE username= ?",
                (username,),
            )
            user = cursor.fetchone()
        except sqlite3.OperationalError:
            cursor.execute(
                "SELECT password_hash, role FROM staff WHERE username= ?",
                (username,),
            )
            base = cursor.fetchone()
            user = (0, base[0], base[1], 1, 0) if base else None
        conn.close()

        if user:
            user_id, stored_hash, role, is_active, must_change_password = user

            if int(is_active or 1) != 1:
                st.error("This user account is disabled. Contact admin.")
            elif verify_password(password, stored_hash):
                if int(must_change_password or 0) == 1:
                    st.session_state.pending_password_change = True
                    st.session_state.pending_user_id = int(user_id)
                    st.session_state.pending_username = username
                    st.session_state.pending_role = role
                    st.rerun()
                else:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = role
                    update_activity()
                    show_success_summary(
                        "Login successful.",
                        [
                            ("User", username),
                            ("Role", role),
                        ],
                    )
                    st.rerun()
            else:
                st.error("Invalid username or password")
        else:
            st.error("Invalid username or password")

def sync_product_stock(cur, product_id):
    cur.execute(
        """
        SELECT COALESCE(SUM(quantity), 0)
        FROM product_sizes
        WHERE product_id = ?
        """,
        (product_id,)
    )

    total_stock = cur.fetchone()[0]

    cur.execute(
        """
        UPDATE products
        SET stock = ?
        WHERE id = ?
        """,
        (total_stock, product_id)
    )

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

def reset_form_state_by_prefix(prefixes, keep_keys=None):
    keep = set(keep_keys or [])
    for state_key in list(st.session_state.keys()):
        if state_key in keep:
            continue
        if any(state_key.startswith(prefix) for prefix in prefixes):
            st.session_state.pop(state_key, None)

  
# ----------------------------
# POS LOGIC
# ----------------------------
def pos_screen(show_prices=False):
    update_activity()
    pos_form_version = "2026_03_04_placeholders_v1"
    if st.session_state.get("pos_form_version") != pos_form_version:
        reset_form_state_by_prefix(["pos_"], keep_keys=[])
        st.session_state["pos_form_version"] = pos_form_version
        st.session_state["pos_paid_time_mode"] = "Select Time"
    pos_logo_markup = ""
    try:
        logo_path = get_brand_logo_path()
        if logo_path:
            with open(logo_path, "rb") as f:
                logo_b64 = base64.b64encode(f.read()).decode("ascii")
            pos_logo_markup = (
                "<div class='sn-pos-logo'>"
                f"<img src='data:image/png;base64,{logo_b64}' alt='Shoes Nexus Logo'/>"
                "</div>"
            )
    except Exception:
        pos_logo_markup = ""

    st.markdown(
        f"""
        <div class='sn-pos-head'>
            <h2>Shoes Nexus POS</h2>
            {pos_logo_markup}
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.session_state.get("flash_sale_success"):
        saved = st.session_state.get("flash_sale_payload", {})
        show_success_summary(
            "Sale recorded successfully.",
            [
                ("Sale ID", int(saved.get("sale_id", 0) or 0)),
                ("Date", str(saved.get("sale_date", ""))),
                ("Time Paid", str(saved.get("paid_time", ""))),
                ("Product", str(saved.get("product", ""))),
                ("Size", str(saved.get("size", ""))),
                ("Quantity", int(saved.get("quantity", 0) or 0)),
                ("Gross (KES)", f"{int(saved.get('gross_revenue', 0) or 0):,}"),
                ("Discount (KES)", f"{int(saved.get('discount_amount', 0) or 0):,}"),
                ("Net Revenue (KES)", f"{int(saved.get('net_revenue', 0) or 0):,}"),
                ("Payment", str(saved.get("payment_mode", ""))),
                ("Source", str(saved.get("source", ""))),
                ("Fulfillment", str(saved.get("fulfillment_type", ""))),
            ],
        )
        st.session_state.flash_sale_success = False
    if st.session_state.get("flash_broker_sale_success"):
        saved = st.session_state.get("flash_broker_sale_payload", {})
        show_success_summary(
            "Brokered sale recorded successfully.",
            [
                ("Sale ID", int(saved.get("sale_id", 0) or 0)),
                ("Date", str(saved.get("sale_date", ""))),
                ("Time Paid", str(saved.get("paid_time", ""))),
                ("Category", str(saved.get("category", ""))),
                ("Brand", str(saved.get("brand", ""))),
                ("Model", str(saved.get("model", ""))),
                ("Color", str(saved.get("color", ""))),
                ("Quantity", int(saved.get("quantity", 0) or 0)),
                ("Gross (KES)", f"{int(saved.get('gross_revenue', 0) or 0):,}"),
                ("Discount (KES)", f"{int(saved.get('discount_amount', 0) or 0):,}"),
                ("Net Revenue (KES)", f"{int(saved.get('net_revenue', 0) or 0):,}"),
                ("Payment", str(saved.get("payment_mode", ""))),
                ("Fulfillment", str(saved.get("fulfillment_type", ""))),
            ],
        )
        st.session_state.flash_broker_sale_success = False
    if "active_customer_session_id" not in st.session_state:
        st.session_state.active_customer_session_id = None
    session_col, clear_col = st.columns([3, 1], gap="small")
    with session_col:
        st.markdown(
            f"<div style='color:#1f2937;font-weight:600;'>Active customer session: {st.session_state.active_customer_session_id or 'None'}</div>",
            unsafe_allow_html=True,
        )
    with clear_col:
        if st.button("Next Customer", key="pos_next_customer"):
            st.session_state.active_customer_session_id = None
            reset_form_state_by_prefix(["pos_"], keep_keys=[])
            st.session_state["pos_paid_time_mode"] = "Select Time"
            st.rerun()

    with st.expander("Brokered Sale (Profit Only)", expanded=False):
        broker_category = st.selectbox(
            "Category",
            ["Men", "Women", "Accessories", "Other"],
            key="broker_category"
        )
        broker_brand = st.text_input("Brand (e.g. Casio, Timberland)", key="broker_brand")
        broker_model = st.text_input("Model / Item", key="broker_model")
        broker_color = st.text_input("Color / Variant", key="broker_color")
        broker_profit = st.number_input(
            "Profit per item (KES)",
            min_value=0,
            step=50,
            key="broker_profit"
        )
        broker_qty = st.number_input(
            "Quantity",
            min_value=1,
            step=1,
            key="broker_qty"
        )
        broker_total = int(broker_profit) * int(broker_qty)
        st.markdown(
            f"<div style='margin:.25rem 0 .35rem 0;color:#111318;font-weight:700;'>Total profit (KES): {broker_total:,}</div>",
            unsafe_allow_html=True,
        )
        broker_payment_mode = st.radio(
            "Payment Mode",
            ["CASH", "MPESA", "MIXED"],
            horizontal=True,
            key="broker_payment_mode"
        )
        broker_paid_time = render_required_time_paid(
            "broker_paid_time_mode",
            "broker_paid_time",
        )
        broker_fulfillment = st.selectbox(
            "Fulfillment",
            ["In-store Pickup", "Delivery"],
            key="broker_fulfillment",
        )
        broker_delivery_option = ""
        broker_delivery_location = ""
        if broker_fulfillment == "Delivery":
            bd_col1, bd_col2 = st.columns(2)
            with bd_col1:
                broker_delivery_option = st.text_input(
                    "Rider / Delivery Option Used",
                    key="broker_delivery_option",
                    placeholder="Rider name, in-house rider, Bolt, Uber, etc.",
                ).strip()
            with bd_col2:
                broker_delivery_location = st.text_input(
                    "Delivery Location",
                    key="broker_delivery_location",
                    placeholder="Estate, area, landmark, or town",
                ).strip()
        broker_discount_type = st.selectbox(
            "Discount Type",
            ["None", "Cash Amount", "Percentage"],
            key="broker_discount_type",
        )
        broker_discount_value = 0.0
        if broker_discount_type == "Cash Amount":
            broker_discount_value = st.number_input(
                "Discount Amount (KES)",
                min_value=0.0,
                step=50.0,
                key="broker_discount_cash",
            )
        elif broker_discount_type == "Percentage":
            broker_discount_value = st.number_input(
                "Discount Percentage (%)",
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                key="broker_discount_pct",
            )
        broker_gross = float(int(broker_profit) * int(broker_qty))
        if broker_discount_type == "Cash Amount":
            broker_discount_amount = min(float(broker_discount_value), broker_gross)
        elif broker_discount_type == "Percentage":
            broker_discount_amount = round((broker_gross * float(broker_discount_value)) / 100.0, 2)
        else:
            broker_discount_amount = 0.0
        broker_net = max(broker_gross - broker_discount_amount, 0.0)
        st.markdown(
            f"<div style='margin:.25rem 0 .35rem 0;color:#111318;font-weight:700;'>Net amount payable (KES): {int(broker_net):,}</div>",
            unsafe_allow_html=True,
        )
        broker_cash_amount = 0.0
        broker_mpesa_amount = 0.0
        if broker_payment_mode == "MIXED":
            c_cash, c_mpesa = st.columns(2)
            with c_cash:
                broker_cash_amount = st.number_input(
                    "Cash Amount (KES)",
                    min_value=0.0,
                    step=50.0,
                    key="broker_cash_amount",
                )
            with c_mpesa:
                broker_mpesa_amount = st.number_input(
                    "M-Pesa Amount (KES)",
                    min_value=0.0,
                    step=50.0,
                    key="broker_mpesa_amount",
                )
        elif broker_payment_mode == "CASH":
            broker_cash_amount = broker_net
        else:
            broker_mpesa_amount = broker_net
        broker_notes = st.text_area("Notes (optional)", key="broker_notes")
        broker_same_customer = st.checkbox(
            "Add brokered line to current customer session",
            key="broker_same_customer",
        )

        if st.button(" Record Brokered Sale"):
            if broker_profit <= 0:
                st.error(" Profit must be greater than 0.")
                st.stop()
            if not broker_model.strip():
                st.error(" Item description is required.")
                st.stop()
            brokered_product_id = get_or_create_brokered_product()
            if broker_fulfillment == "Delivery" and not broker_delivery_option:
                st.error(" Rider / delivery option is required for delivery orders.")
                st.stop()
            if broker_fulfillment == "Delivery" and not broker_delivery_location:
                st.error(" Delivery location is required for delivery orders.")
                st.stop()
            if broker_payment_mode == "MIXED":
                if round(float(broker_cash_amount) + float(broker_mpesa_amount), 2) != round(float(broker_net), 2):
                    st.error(" Mixed payment totals must equal net amount payable.")
                    st.stop()
            if broker_paid_time is None:
                st.error(" Please select Time Paid.")
                st.stop()
            revenue = int(broker_net)
            conn = get_db()
            cur = conn.cursor()
            try:
                if broker_same_customer:
                    customer_session_id = st.session_state.active_customer_session_id
                    if not customer_session_id:
                        st.error(" No active customer session. Record a new customer item first.")
                        st.stop()
                    customer_count_unit = 0
                else:
                    customer_session_id = generate_customer_session_id()
                    st.session_state.active_customer_session_id = customer_session_id
                    customer_count_unit = 1
                cur.execute(
                    """
                    INSERT INTO sales
                    (product_id, size, quantity, revenue, cost, payment_method, source, sale_date, sale_time, paid_time, fulfillment_type, delivery_option, delivery_location, payment_cash_amount, payment_mpesa_amount, discount_type, discount_value, discount_amount, gross_revenue, customer_session_id, customer_count_unit, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, date('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        brokered_product_id,
                        "N/A",
                        int(broker_qty),
                        revenue,
                        0,
                        str(broker_payment_mode),
                        "Brokered",
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
                st.session_state.active_customer_session_id = None
                reset_form_state_by_prefix(["broker_"], keep_keys=[])
                st.session_state["broker_paid_time_mode"] = "Select Time"
                st.session_state.flash_broker_sale_payload = {
                    "sale_id": int(cur.lastrowid or 0),
                    "sale_date": datetime.now().strftime("%Y-%m-%d"),
                    "paid_time": broker_paid_time.strftime("%H:%M:%S"),
                    "category": broker_category,
                    "brand": broker_brand,
                    "model": broker_model,
                    "color": broker_color,
                    "quantity": int(broker_qty),
                    "gross_revenue": int(broker_gross),
                    "discount_amount": int(broker_discount_amount),
                    "net_revenue": int(revenue),
                    "payment_mode": broker_payment_mode,
                    "fulfillment_type": broker_fulfillment,
                }
                st.session_state.flash_broker_sale_success = True
                st.rerun()
            except Exception as e:
                conn.rollback()
                st.error(f" Error recording brokered sale: {e}")
            finally:
                conn.close()

    # Admin-only cancel sale (with safeguards)
    if st.session_state.get("role") == "Admin":
        with st.expander(" Cancel Sale (Admin Only)", expanded=False):
            if st.session_state.get("cancel_sale_flash"):
                saved = st.session_state.get("cancel_sale_last_saved", {})
                show_success_summary(
                    "Sale cancelled.",
                    [
                        ("Sale ID", int(saved.get("sale_id", 0) or 0)),
                        ("Date", str(saved.get("sale_date", ""))),
                        ("Product", str(saved.get("product", ""))),
                        ("Size", str(saved.get("size", ""))),
                        ("Quantity", int(saved.get("quantity", 0) or 0)),
                        ("Revenue (KES)", f"{int(saved.get('revenue', 0) or 0):,}"),
                        ("Status", "CANCELLED"),
                    ],
                )
                st.session_state.cancel_sale_flash = False

            st.warning("This will permanently remove a sale and reverse stock (if applicable).")
            lookup_conn = get_db()
            cancel_sales_df = pd.read_sql(
                """
                SELECT
                    s.id AS sale_id,
                    s.sale_date,
                    COALESCE(p.brand, 'Unknown') AS brand,
                    COALESCE(p.model, 'Unknown') AS model,
                    COALESCE(s.size, 'N/A') AS size,
                    COALESCE(s.quantity, 0) AS quantity,
                    COALESCE(s.revenue, 0) AS revenue,
                    COALESCE(s.payment_method, '') AS payment_method
                FROM sales s
                LEFT JOIN products p ON p.id = s.product_id
                ORDER BY s.id DESC
                LIMIT 200
                """,
                lookup_conn,
            )
            lookup_conn.close()
            if cancel_sales_df.empty:
                st.info("No sales available to cancel.")
                return

            cancel_nonce = int(st.session_state.get("cancel_sale_nonce", 0))
            sale_key = f"cancel_sale_selected_id_{cancel_nonce}"
            confirm_key = f"cancel_sale_confirm_{cancel_nonce}"
            check_key = f"cancel_sale_check_{cancel_nonce}"

            sale_id = st.selectbox(
                "Select Sale to Cancel",
                cancel_sales_df["sale_id"].tolist(),
                index=None,
                placeholder="Select sale",
                format_func=lambda x: (
                    f"#{int(x)} | {cancel_sales_df[cancel_sales_df['sale_id'] == x]['sale_date'].iloc[0]} | "
                    f"{cancel_sales_df[cancel_sales_df['sale_id'] == x]['brand'].iloc[0]} "
                    f"{cancel_sales_df[cancel_sales_df['sale_id'] == x]['model'].iloc[0]} | "
                    f"Size {cancel_sales_df[cancel_sales_df['sale_id'] == x]['size'].iloc[0]} | "
                    f"Qty {int(cancel_sales_df[cancel_sales_df['sale_id'] == x]['quantity'].iloc[0])} | "
                    f"KES {int(cancel_sales_df[cancel_sales_df['sale_id'] == x]['revenue'].iloc[0])} | "
                    f"{cancel_sales_df[cancel_sales_df['sale_id'] == x]['payment_method'].iloc[0]}"
                ),
                key=sale_key,
            )
            selected_row = None
            if sale_id is not None:
                selected_row = cancel_sales_df[cancel_sales_df["sale_id"] == int(sale_id)].iloc[0]
            confirm_text = st.text_input("Type CANCEL SALE to confirm", key=confirm_key)
            confirm_check = st.checkbox("I understand this cannot be undone", key=check_key)

            if st.button(" Cancel Sale", type="primary", disabled=(sale_id is None)):
                if confirm_text.strip().upper() != "CANCEL SALE" or not confirm_check:
                    st.error(" Confirmation required.")
                    st.stop()

                conn = get_db()
                cur = conn.cursor()
                try:
                    cur.execute(
                        """
                        SELECT product_id, size, quantity
                        FROM sales
                        WHERE id = ?
                        """,
                        (int(sale_id),),
                    )
                    row = cur.fetchone()
                    if not row:
                        st.error(" Sale not found.")
                        conn.close()
                        st.stop()

                    product_id, size, quantity = row

                    # Remove related pending return requests for this sale
                    cur.execute(
                        """
                        DELETE FROM returns_exchanges
                        WHERE sale_id = ? AND status = 'PENDING'
                        """,
                        (int(sale_id),),
                    )

                    # Restore stock if size is real (skip brokered)
                    if size and str(size).upper() != "N/A":
                        cur.execute(
                            """
                            INSERT INTO product_sizes (product_id, size, quantity)
                            VALUES (?, ?, 0)
                            ON CONFLICT(product_id, size) DO NOTHING
                            """,
                            (int(product_id), str(size)),
                        )
                        cur.execute(
                            """
                            UPDATE product_sizes
                            SET quantity = quantity + ?
                            WHERE product_id = ? AND size = ?
                            """,
                            (int(quantity), int(product_id), str(size)),
                        )
                        sync_product_stock(cur, int(product_id))

                    # Delete the sale
                    cur.execute("DELETE FROM sales WHERE id = ?", (int(sale_id),))

                    # Log activity
                    cur.execute(
                        """
                        INSERT INTO activity_log
                        (event_type, reference_id, role, username, message)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            "SALE_CANCELLED",
                            int(sale_id),
                            "Admin",
                            st.session_state.username,
                            f"Cancelled sale ID {int(sale_id)}",
                        ),
                    )

                    conn.commit()
                    st.session_state.cancel_sale_last_saved = {
                        "sale_id": int(sale_id),
                        "sale_date": str(selected_row.get("sale_date", "")),
                        "product": f"{selected_row.get('brand', '')} {selected_row.get('model', '')}".strip(),
                        "size": str(selected_row.get("size", "")),
                        "quantity": int(selected_row.get("quantity", 0) or 0),
                        "revenue": int(selected_row.get("revenue", 0) or 0),
                    }
                    st.session_state.cancel_sale_flash = True
                    st.session_state.cancel_sale_nonce = cancel_nonce + 1
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f" Error cancelling sale: {e}")
                finally:
                    conn.close()

    conn = get_db()

    # ----------------------------
    # LOAD PRODUCTS
    # ----------------------------
    products_df = pd.read_sql(
        """
        SELECT id, brand, model, color, category, selling_price, buying_price
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
        return

    # Normalize optional text fields so search and display don't break on NULLs.
    for col in ["brand", "model", "color"]:
        products_df[col] = products_df[col].fillna("").astype(str)

    search_query = st.text_input(
        "Search item in inventory",
        placeholder="Type brand, model, or color...",
        key="pos_search_query",
    )
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
            return

    if q:
        st.caption(f"Found {len(products_df)} matching product record(s).")

    brand_values = sorted(products_df["brand"].dropna().astype(str).unique().tolist())
    if not brand_values:
        st.warning("No brands available.")
        conn.close()
        return
    brand_options = ["Select brand"] + brand_values
    selected_brand = st.selectbox("Select Brand", brand_options, key="pos_brand")
    if selected_brand == "Select brand":
        conn.close()
        return

    models_df = products_df[products_df["brand"] == selected_brand].copy()
    model_values = sorted(models_df["model"].dropna().astype(str).unique().tolist())
    if not model_values:
        st.warning("No models available for selected brand.")
        conn.close()
        return
    model_options = ["Select model"] + model_values
    selected_model = st.selectbox("Select Model", model_options, key="pos_model")
    if selected_model == "Select model":
        conn.close()
        return

    colors_df = models_df[models_df["model"] == selected_model].copy()
    color_values = sorted(colors_df["color"].dropna().astype(str).unique().tolist())
    if not color_values:
        st.warning("No colors available for selected model.")
        conn.close()
        return
    color_options = ["Select color"] + color_values
    selected_color = st.selectbox("Select Color", color_options, key="pos_color")
    if selected_color == "Select color":
        conn.close()
        return

    product = colors_df[colors_df["color"] == selected_color].iloc[0]
    product_id = int(product["id"])
    selected_product = f"{selected_brand} {selected_model} ({selected_color})"

    sell_price = int(product["selling_price"])
    buy_price = product["buying_price"]

    # ----------------------------
    # LOAD SIZES
    # ----------------------------
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

    #  Remove zero-stock sizes
    sizes_df = sizes_df[sizes_df["quantity"] > 0]

    if sizes_df.empty:
        st.info(" This product is SOLD OUT.")
        conn.close()
        return


    size_options = ["Select size"] + sizes_df["size"].astype(str).tolist()

    size = st.selectbox("Select Size", size_options, key="pos_size")

    quantity = st.number_input(
        "Quantity",
        min_value=0,
        step=1,
        key="pos_quantity"
    )

    payment_mode = st.radio(
        "Payment Mode",
        ["CASH", "MPESA", "MIXED"],
        horizontal=True,
        key="pos_payment_mode",
    )
    paid_time = render_required_time_paid(
        "pos_paid_time_mode",
        "pos_paid_time",
    )
    fulfillment_type = st.selectbox(
        "Fulfillment",
        ["In-store Pickup", "Delivery"],
        key="pos_fulfillment_type",
    )
    delivery_option = ""
    delivery_location = ""
    if fulfillment_type == "Delivery":
        d_col1, d_col2 = st.columns(2)
        with d_col1:
            delivery_option = st.text_input(
                "Rider / Delivery Option Used",
                key="pos_delivery_option",
                placeholder="Rider name, in-house rider, Bolt, Uber, etc.",
            ).strip()
        with d_col2:
            delivery_location = st.text_input(
                "Delivery Location",
                key="pos_delivery_location",
                placeholder="Estate, area, landmark, or town",
            ).strip()

    source = st.selectbox(
        "Customer Source",
        [
            "In-store Walkins",
            "Facebook",
            "Instagram",
            "TikTok",
            "Twitter",
            "Website",
            "Referral/Returning Customer",
            "Other"
        ],
        key="pos_source",
    )

    discount_type = st.selectbox(
        "Discount Type",
        ["None", "Cash Amount", "Percentage"],
        key="pos_discount_type",
    )
    discount_value = 0.0
    if discount_type == "Cash Amount":
        discount_value = st.number_input(
            "Discount Amount (KES)",
            min_value=0.0,
            step=50.0,
            key="pos_discount_cash",
        )
    elif discount_type == "Percentage":
        discount_value = st.number_input(
            "Discount Percentage (%)",
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            key="pos_discount_pct",
        )
    gross_revenue = float(int(quantity) * int(sell_price))
    if discount_type == "Cash Amount":
        discount_amount = min(float(discount_value), gross_revenue)
    elif discount_type == "Percentage":
        discount_amount = round((gross_revenue * float(discount_value)) / 100.0, 2)
    else:
        discount_amount = 0.0
    net_revenue = max(gross_revenue - discount_amount, 0.0)
    st.markdown(
        f"<div style='margin:.25rem 0 .35rem 0;color:#111318;font-weight:700;'>Net amount payable (KES): {int(net_revenue):,}</div>",
        unsafe_allow_html=True,
    )
    cash_amount = 0.0
    mpesa_amount = 0.0
    if payment_mode == "MIXED":
        c_cash, c_mpesa = st.columns(2)
        with c_cash:
            cash_amount = st.number_input(
                "Cash Amount (KES)",
                min_value=0.0,
                step=50.0,
                key="pos_cash_amount",
            )
        with c_mpesa:
            mpesa_amount = st.number_input(
                "M-Pesa Amount (KES)",
                min_value=0.0,
                step=50.0,
                key="pos_mpesa_amount",
            )
    elif payment_mode == "CASH":
        cash_amount = net_revenue
    else:
        mpesa_amount = net_revenue

    notes = st.text_area(" Sales Notes (optional)", key="pos_notes")
    same_customer = st.checkbox(
        "Add this sale as another line item for current customer",
        key="pos_same_customer_regular",
    )

    st.markdown(
        f"<div style='margin:.25rem 0 .35rem 0;color:#111318;font-weight:700;'>Selling price: KES {int(sell_price):,}</div>",
        unsafe_allow_html=True,
    )

    sell_clicked = st.button(" SELL")

    # ==========================================================
    # SELL LOGIC  IMPOSSIBLE TO BYPASS
    # ==========================================================
    if sell_clicked:

        error = False

        if size == "Select size":
            st.error(" Please select a size.")
            error = True

        if quantity <= 0:
            st.error(" Quantity must be greater than 0.")
            error = True

        row = sizes_df[sizes_df["size"].astype(str) == size]

        if row.empty:
            st.error(f" No stock found for size {size}.")
            error = True
        else:
            size_stock = int(row["quantity"].iloc[0])
            if quantity > size_stock:
                st.error(f" Only {size_stock} pairs available for size {size}.")
                error = True

        # ----------------------------
        # EXECUTE SALE (ONLY IF VALID)
        # ----------------------------
        if not error:
            unit_cost = pd.to_numeric(pd.Series([buy_price]), errors="coerce").iloc[0]
            if pd.isna(unit_cost) or float(unit_cost) <= 0:
                st.error(" Buying price is missing for this product. Update buying price before selling.")
                conn.close()
                return

            if fulfillment_type == "Delivery" and not delivery_option:
                st.error(" Rider / delivery option is required for delivery orders.")
                conn.close()
                return
            if fulfillment_type == "Delivery" and not delivery_location:
                st.error(" Delivery location is required for delivery orders.")
                conn.close()
                return
            if payment_mode == "MIXED":
                if round(float(cash_amount) + float(mpesa_amount), 2) != round(float(net_revenue), 2):
                    st.error(" Mixed payment totals must equal net amount payable.")
                    conn.close()
                    return
            if paid_time is None:
                st.error(" Please select Time Paid.")
                conn.close()
                return

            revenue = int(net_revenue)

            cur = conn.cursor()
            #  SAFETY CHECK: product still active
            cur.execute(
                "SELECT is_active FROM products WHERE id = ?",
                (product_id,)
            )
            if cur.fetchone()[0] != 1:
                st.error(" This product is no longer active and cannot be sold.")
                conn.close()
                return

            # Deduct size stock
            cur.execute(
                """
                UPDATE product_sizes
                SET quantity = quantity - ?
                WHERE product_id = ? AND size = ?
                """,
                (quantity, product_id, size)
            )

            # Sync main product stock
            sync_product_stock(cur, product_id)

            if same_customer:
                customer_session_id = st.session_state.active_customer_session_id
                if not customer_session_id:
                    conn.rollback()
                    conn.close()
                    st.error(" No active customer session. Record a new customer item first.")
                    return
                customer_count_unit = 0
            else:
                customer_session_id = generate_customer_session_id()
                st.session_state.active_customer_session_id = customer_session_id
                customer_count_unit = 1

            cost, unresolved_cost_qty = consume_stock_cost_layers(
                cur,
                int(product_id),
                str(size),
                int(quantity),
                float(unit_cost),
            )
            if unresolved_cost_qty > 0:
                conn.rollback()
                conn.close()
                st.error(" Missing cost layers and no valid fallback buying price for this sale.")
                return

            # Record sale
            cur.execute(
                """
                INSERT INTO sales
                (product_id, size, quantity, revenue, cost, payment_method, source, sale_date, sale_time, paid_time, fulfillment_type, delivery_option, delivery_location, payment_cash_amount, payment_mpesa_amount, discount_type, discount_value, discount_amount, gross_revenue, customer_session_id, customer_count_unit, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, date('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    size,
                    quantity,
                    revenue,
                    cost,
                    payment_mode,
                    source,
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
            sale_id = cur.lastrowid
            cur.execute(
                """
                INSERT INTO activity_log
                (event_type, reference_id, role, username, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "SALE_RECORDED",
                    int(sale_id),
                    st.session_state.get("role", "Unknown"),
                    st.session_state.get("username", "unknown"),
                    f"Sale recorded: Product {int(product_id)}, Size {size}, Qty {int(quantity)}, Revenue KES {int(revenue)}, Cost KES {int(cost)}"
                )
            )

            conn.commit()

            st.session_state.active_customer_session_id = None
            reset_form_state_by_prefix(["pos_"], keep_keys=[])
            st.session_state["pos_paid_time_mode"] = "Select Time"
            st.session_state.flash_sale_payload = {
                "sale_id": int(sale_id),
                "sale_date": datetime.now().strftime("%Y-%m-%d"),
                "paid_time": paid_time.strftime("%H:%M:%S"),
                "product": selected_product,
                "size": size,
                "quantity": int(quantity),
                "gross_revenue": int(gross_revenue),
                "discount_amount": int(discount_amount),
                "net_revenue": int(revenue),
                "payment_mode": payment_mode,
                "source": source,
                "fulfillment_type": fulfillment_type,
            }
            st.session_state.flash_sale_success = True
            st.rerun()

    conn.close()

def get_size_inventory():
    conn = get_db()
    df = pd.read_sql(
        """
        SELECT 
            p.id AS product_id,
            p.brand,
            p.model,
            p.color,
            ps.size,
            ps.quantity
        FROM product_sizes ps
        JOIN products p ON p.id = ps.product_id
        ORDER BY p.id, ps.size
        """,
        conn
    )
    conn.close()
    return df

# ----------------------------
# INVENTORY VIEW
#size stock alerts
def size_stock_alerts(role, threshold=2):
    st.subheader(" Low Stock Alerts (By Size)")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            p.brand,
            p.model,
            p.color,
            ps.size,
            ps.quantity
        FROM product_sizes ps
        JOIN products p ON p.id = ps.product_id
        WHERE ps.quantity <= ?
        ORDER BY ps.quantity ASC
        """,
        conn,
        params=(threshold,)
    )
    conn.close()

    if df.empty:
        st.success("All size stocks are healthy ")
        return

    st.warning(f" Sizes with stock  {threshold}")

    if role == "Cashier":
        view = df[["brand", "model", "color", "size", "quantity"]]
    else:
        view = df

    st.dataframe(
        view,
        hide_index=True,
        use_container_width=True
    )

#zero size stock alerts
def zero_size_stock_alerts(role):
    st.subheader(" Out-of-Stock Sizes")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            p.brand,
            p.model,
            p.color,
            ps.size,
            ps.quantity
        FROM product_sizes ps
        JOIN products p ON p.id = ps.product_id
        WHERE ps.quantity = 0
        ORDER BY p.brand, p.model, ps.size
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.success("No out-of-stock sizes ")
        return

    st.error(" These sizes are OUT OF STOCK")

    if role == "Cashier":
        view = df[["brand", "model", "color", "size"]]
    else:
        view = df

    st.dataframe(
        view,
        hide_index=True,
        use_container_width=True
    )

#most sold sizes per product
def most_sold_sizes_per_product():
    st.subheader(" Most Sold Sizes per Product")

    conn = get_db()

    df = pd.read_sql(
        """
        SELECT
            p.id AS product_id,
            p.brand,
            p.model,
            p.color,
            s.size,
            SUM(s.net_quantity) AS total_sold
        FROM net_sales s
        JOIN products p ON p.id = s.product_id
        GROUP BY
            p.id,
            p.brand,
            p.model,
            p.color,
            s.size
        ORDER BY
            p.brand,
            p.model,
            total_sold DESC
        """,
        conn
    )

    conn.close()

    if df.empty:
        st.info("No sales data available yet.")
        return

    # Group by product
    grouped = df.groupby(["product_id", "brand", "model", "color"])

    for (pid, brand, model, color), group in grouped:
        st.markdown(f"** {brand} {model} ({color})**")
        view = group[["size", "total_sold"]].copy()
        view["total_sold"] = view["total_sold"].astype(int)
        st.dataframe(
            view,
            hide_index=True,
            use_container_width=True
        )
        st.divider()

#most sold sizes by gender
def most_sold_sizes_by_gender():
    st.subheader(" Overall Most Sold Sizes (Men vs Women)")

    conn = get_db()

    df = pd.read_sql(
        """
        SELECT
            p.category,
            s.size,
            SUM(s.net_quantity) AS total_sold
        FROM net_sales s
        JOIN products p ON p.id = s.product_id
        WHERE p.category IS NOT NULL
        GROUP BY
            p.category,
            s.size
        ORDER BY
            p.category,
            total_sold DESC
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.info("No sales data available yet.")
        return

    df["total_sold"] = df["total_sold"].astype(int)
    df["category"] = df["category"].str.capitalize()

    col1, col2 = st.columns(2)

    # ---------------- MEN ----------------
    with col1:
        st.markdown("###  Men  Most Sold Sizes")
        men = df[df["category"] == "Men"]

        if men.empty:
            st.info("No men sales recorded.")
        else:
            st.dataframe(
                men[["size", "total_sold"]],
                hide_index=True,
                use_container_width=True
            )

    # ---------------- WOMEN ----------------
    with col2:
        st.markdown("###  Women  Most Sold Sizes")
        women = df[df["category"] == "Women"]

        if women.empty:
            st.info("No women sales recorded.")
        else:
            st.dataframe(
                women[["size", "total_sold"]],
                hide_index=True,
                use_container_width=True
            )

#dead stock - recommended for discounts
def dead_sizes_alerts():
    st.subheader(" Dead Sizes Alert (No Sales Recorded)")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            p.brand,
            p.model,
            p.color,
            ps.size,
            ps.quantity AS current_stock,
            COALESCE(SUM(s.quantity - COALESCE(s.returned_quantity, 0)), 0) AS sold_qty
        FROM product_sizes ps
        JOIN products p ON p.id = ps.product_id
        LEFT JOIN sales s
            ON s.product_id = ps.product_id
            AND s.size = ps.size
        GROUP BY p.id, ps.size
        HAVING current_stock > 0 AND sold_qty = 0
        ORDER BY p.brand, p.model, ps.size
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.success(" No dead sizes detected")
        return

    st.warning(" These sizes have stock but ZERO sales")

    st.dataframe(
        df.rename(columns={
            "brand": "Brand",
            "model": "Model",
            "color": "Color",
            "size": "Size",
            "current_stock": "Stock",
            "sold_qty": "Sold Qty"
        }),
        hide_index=True,
        use_container_width=True
    )

    #slow sizes alerts
def slow_sizes_alerts(threshold=5, days=30):
    st.subheader(" Slow Sizes Alert (Low Movement)")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            p.brand,
            p.model,
            p.color,
            ps.size,
            ps.quantity AS current_stock,
            COALESCE(SUM(s.quantity - COALESCE(s.returned_quantity, 0)), 0) AS sold_qty
        FROM product_sizes ps
        JOIN products p ON p.id = ps.product_id
        LEFT JOIN sales s
            ON s.product_id = ps.product_id
            AND s.size = ps.size
            AND s.sale_date >= date('now', ?)
        GROUP BY p.id, ps.size
        HAVING current_stock > 0 AND sold_qty <= ?
        ORDER BY sold_qty ASC, p.brand, p.model, ps.size
        """,
        conn,
        params=(f"-{days} days", threshold)
    )
    conn.close()

    if df.empty:
        st.success(" No slow sizes detected")
        return

    st.warning(
        f" Sizes sold  {threshold} unit(s) in the last {days} days"
    )

    st.dataframe(
        df.rename(columns={
            "brand": "Brand",
            "model": "Model",
            "color": "Color",
            "size": "Size",
            "current_stock": "Stock",
            "sold_qty": "Sold (Last 30 Days)"
        }),
        hide_index=True,
        use_container_width=True
    )

#discount suggestions
def discount_suggestions(days_slow=30, days_dead=60):
    st.subheader(" Discount Suggestions (Slow & Dead Sizes)")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            p.brand,
            p.model,
            p.color,
            ps.size,
            ps.quantity AS current_stock,

            COALESCE(SUM(
                CASE 
                    WHEN s.sale_date >= date('now', ?) THEN (s.quantity - COALESCE(s.returned_quantity, 0))
                    ELSE 0
                END
            ), 0) AS sold_30,

            COALESCE(SUM(
                CASE 
                    WHEN s.sale_date >= date('now', ?) THEN (s.quantity - COALESCE(s.returned_quantity, 0))
                    ELSE 0
                END
            ), 0) AS sold_60

        FROM product_sizes ps
        JOIN products p ON p.id = ps.product_id
        LEFT JOIN sales s
            ON s.product_id = ps.product_id
            AND s.size = ps.size
        GROUP BY p.id, ps.size
        HAVING current_stock > 0
        """,
        conn,
        params=(f"-{days_slow} days", f"-{days_dead} days")
    )
    conn.close()

    if df.empty:
        st.success(" No discount suggestions available")
        return

    def classify(row):
        if row["sold_60"] == 0:
            return "DEAD", "3050%"
        elif row["sold_30"] <= 2:
            return "SLOW", "1020%"
        return None, None

    df[["Status", "Suggested Discount"]] = df.apply(
        lambda r: pd.Series(classify(r)),
        axis=1
    )

    df = df[df["Status"].notna()]

    if df.empty:
        st.success(" No slow or dead sizes detected")
        return

    st.warning(" Discount action recommended")

    st.dataframe(
        df.rename(columns={
            "brand": "Brand",
            "model": "Model",
            "color": "Color",
            "size": "Size",
            "current_stock": "Stock",
            "sold_30": "Sold (30d)",
            "sold_60": "Sold (60d)"
        })[
            [
                "Brand", "Model", "Color", "Size",
                "Stock", "Sold (30d)", "Sold (60d)",
                "Status", "Suggested Discount"
            ]
        ],
        hide_index=True,
        use_container_width=True
    )

# ----------------------------
# STOCK ALERTS
# ----------------------------
def stock_alerts():
    st.subheader(" Low Stock Alerts")

    conn = get_db()
    df = pd.read_sql("SELECT * FROM products", conn)
    conn.close()

    df["stock"] = df["stock"].apply(
        lambda x: 0 if pd.isna(x) else (int.from_bytes(x, "little") if isinstance(x, bytes) else int(x))
    )

    alerts = df[df["stock"] <= df["reorder_level"]]

    if alerts.empty:
        st.success("All stock levels are healthy ")
    else:
        st.warning("Reorder required:")
    st.dataframe(
            alerts[["id", "brand", "model", "color", "stock", "reorder_level"]],
            hide_index=True,
            use_container_width=True,
        )

def product_audit_filter():
    st.subheader("Product Audit Filter")
    st.caption("Select a product, audit period, and optional size to trace sales and compare with current system stock.")

    conn = get_db()
    products = pd.read_sql(
        """
        SELECT id, brand, model, color
        FROM products
        ORDER BY brand, model, color
        """,
        conn,
    )
    conn.close()

    if products.empty:
        st.info("No products available for audit.")
        return

    product_options = ["-- Select product --"] + products["id"].astype(str).tolist()
    if st.session_state.get("audit_product_id") not in product_options:
        st.session_state["audit_product_id"] = "-- Select product --"

    selected_product = st.selectbox(
        "Product",
        product_options,
        format_func=lambda x: (
            x
            if x == "-- Select product --"
            else (
                products[products["id"] == int(x)][["brand", "model", "color"]]
                .iloc[0]
                .to_string()
            )
        ),
        key="audit_product_id",
    )

    today = pd.Timestamp.today().normalize()
    month_start = today.replace(day=1).date()
    a1, a2 = st.columns(2)
    with a1:
        audit_start = st.date_input("Audit Start", month_start, key="audit_start_date")
    with a2:
        audit_end = st.date_input("Audit End", today.date(), key="audit_end_date")

    if audit_start > audit_end:
        st.error("Audit start date cannot be after end date.")
        return

    if selected_product == "-- Select product --":
        st.info("Select a product to run audit.")
        return

    product_id = int(selected_product)
    conn = get_db()
    size_df = pd.read_sql(
        """
        SELECT size, quantity
        FROM product_sizes
        WHERE product_id = ?
        ORDER BY CAST(size AS INTEGER), size
        """,
        conn,
        params=(product_id,),
    )

    size_options = ["All Sizes"]
    if not size_df.empty:
        size_options += sorted(size_df["size"].astype(str).unique().tolist())
    selected_size = st.selectbox("Size Audit", size_options, key="audit_size_filter")

    sales_sql = """
        SELECT
            s.sale_id,
            s.sale_date,
            s.size,
            s.net_quantity AS quantity,
            s.net_revenue AS revenue,
            s.net_cost AS cost,
            s.payment_method,
            s.notes
        FROM net_sales s
        WHERE s.product_id = ?
          AND date(s.sale_date) BETWEEN date(?) AND date(?)
    """
    params = [product_id, str(audit_start), str(audit_end)]
    if selected_size != "All Sizes":
        sales_sql += " AND CAST(s.size AS TEXT) = ?"
        params.append(str(selected_size))
    sales_sql += " ORDER BY s.sale_date DESC, s.sale_id DESC"

    audit_sales = pd.read_sql(sales_sql, conn, params=params)
    conn.close()

    total_units = int(pd.to_numeric(audit_sales.get("quantity", 0), errors="coerce").fillna(0).sum()) if not audit_sales.empty else 0
    total_revenue = int(pd.to_numeric(audit_sales.get("revenue", 0), errors="coerce").fillna(0).sum()) if not audit_sales.empty else 0
    total_cost = int(pd.to_numeric(audit_sales.get("cost", 0), errors="coerce").fillna(0).sum()) if not audit_sales.empty else 0
    total_profit = int(total_revenue - total_cost)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Units Sold", total_units)
    m2.metric("Revenue (KES)", total_revenue)
    m3.metric("Cost (KES)", total_cost)
    m4.metric("Profit (KES)", total_profit)

    st.markdown("### Current System Stock by Size")
    if size_df.empty:
        st.info("No size stock rows found for this product.")
    else:
        stock_view = size_df.copy()
        stock_view["quantity"] = pd.to_numeric(stock_view["quantity"], errors="coerce").fillna(0).astype(int)
        if selected_size != "All Sizes":
            stock_view = stock_view[stock_view["size"].astype(str) == str(selected_size)]
        st.dataframe(
            stock_view.rename(columns={"size": "Size", "quantity": "System Stock"}),
            hide_index=True,
            use_container_width=True,
        )

    st.markdown("### Sales Ledger (Audit Period)")
    if audit_sales.empty:
        st.warning("No sales found for selected product/period/size.")
    else:
        st.dataframe(
            audit_sales.rename(
                columns={
                    "sale_id": "Sale ID",
                    "sale_date": "Sale Date",
                    "size": "Size",
                    "quantity": "Qty",
                    "revenue": "Revenue (KES)",
                    "cost": "Cost (KES)",
                    "payment_method": "Payment Method",
                    "notes": "Notes",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

        csv_data = audit_sales.to_csv(index=False).encode("utf-8")
        st.download_button(
            " Download Product Audit CSV",
            data=csv_data,
            file_name=f"product_audit_{product_id}_{audit_start}_{audit_end}.csv",
            mime="text/csv",
            key="audit_download_csv",
        )

# ----------------------------
# ADMIN REPORTS + CHARTS
# ----------------------------
def build_sales_analytics_pdf(
    start_date,
    end_date,
    sales_type,
    total_revenue,
    total_cost,
    total_profit,
    total_units,
    trend_df,
    top_df,
    payment_series,
    detailed_df,
):
    from io import BytesIO

    def _safe_text(value):
        if value is None:
            return ""
        return str(value)

    def _as_int(value):
        try:
            return int(float(value))
        except Exception:
            return 0

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Shoes Nexus", styles["Title"]))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Sales Analytics Report", styles["Heading2"]))
    elements.append(Spacer(1, 10))
    elements.append(
        Paragraph(
            f"Period: {_safe_text(start_date)} to {_safe_text(end_date)}<br/>"
            f"Sales Type: {_safe_text(sales_type)}",
            styles["Normal"],
        )
    )
    elements.append(Spacer(1, 10))

    kpi_table = Table(
        [
            ["Revenue (KES)", f"{_as_int(total_revenue):,}"],
            ["Cost (KES)", f"{_as_int(total_cost):,}"],
            ["Profit (KES)", f"{_as_int(total_profit):,}"],
            ["Units Sold", f"{_as_int(total_units):,}"],
        ],
        colWidths=[220, 220],
    )
    kpi_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]
        )
    )
    elements.append(kpi_table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Daily Revenue, Cost and Profit", styles["Heading3"]))
    trend_rows = [["Date", "Revenue (KES)", "Cost (KES)", "Profit (KES)"]]
    if trend_df is not None and not trend_df.empty:
        for idx, row in trend_df.iterrows():
            trend_rows.append(
                [
                    _safe_text(pd.to_datetime(idx).strftime("%Y-%m-%d")),
                    f"{_as_int(row.get('revenue', 0)):,}",
                    f"{_as_int(row.get('cost', 0)):,}",
                    f"{_as_int(row.get('profit', 0)):,}",
                ]
            )
    else:
        trend_rows.append(["No data", "-", "-", "-"])
    trend_table = Table(trend_rows, colWidths=[110, 110, 110, 110])
    trend_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    elements.append(trend_table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Top Selling Products", styles["Heading3"]))
    top_rows = [["Product", "Units Sold"]]
    top_slice = top_df.head(10) if top_df is not None else pd.DataFrame()
    if top_slice is not None and not top_slice.empty:
        for _, row in top_slice.iterrows():
            top_rows.append(
                [
                    _safe_text(row.get("product", "")),
                    f"{_as_int(row.get('quantity', 0)):,}",
                ]
            )
    else:
        top_rows.append(["No data", "-"])
    top_table = Table(top_rows, colWidths=[340, 100])
    top_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ]
        )
    )
    elements.append(top_table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Revenue by Payment Method", styles["Heading3"]))
    pay_rows = [["Payment Method", "Revenue (KES)"]]
    if payment_series is not None and len(payment_series) > 0:
        for method, value in payment_series.items():
            pay_rows.append([_safe_text(method), f"{_as_int(value):,}"])
    else:
        pay_rows.append(["No data", "-"])
    pay_table = Table(pay_rows, colWidths=[220, 220])
    pay_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ]
        )
    )
    elements.append(pay_table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Detailed Sales", styles["Heading3"]))
    detail_rows = [["Date", "Brand", "Model", "Size", "Qty", "Revenue", "Cost", "Payment", "Type"]]
    detail_src = detailed_df.copy() if detailed_df is not None else pd.DataFrame()
    if not detail_src.empty:
        limit = 120
        detail_src = detail_src.head(limit)
        for _, row in detail_src.iterrows():
            detail_rows.append(
                [
                    _safe_text(pd.to_datetime(row.get("sale_date")).strftime("%Y-%m-%d")),
                    _safe_text(row.get("brand", ""))[:30],
                    _safe_text(row.get("model", ""))[:30],
                    _safe_text(row.get("size", "")),
                    f"{_as_int(row.get('quantity', 0))}",
                    f"{_as_int(row.get('revenue', 0)):,}",
                    f"{_as_int(row.get('cost', 0)):,}",
                    _safe_text(row.get("payment_method", ""))[:20],
                    _safe_text(row.get("type", ""))[:12],
                ]
            )
        if len(detailed_df) > limit:
            elements.append(
                Paragraph(
                    f"Detailed sales section truncated to first {limit} rows for PDF export.",
                    styles["Italic"],
                )
            )
            elements.append(Spacer(1, 6))
    else:
        detail_rows.append(["No data", "-", "-", "-", "-", "-", "-", "-", "-"])
    detail_table = Table(
        detail_rows,
        colWidths=[52, 68, 68, 34, 30, 58, 50, 58, 42],
        repeatRows=1,
    )
    detail_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("ALIGN", (4, 1), (6, -1), "RIGHT"),
            ]
        )
    )
    elements.append(detail_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def admin_reports():
    st.subheader("Admin Dashboard")

    # ----------------------------
    # DATE FILTERS
    # ----------------------------
    filter_option = st.radio(
        "Select Period",
        ["Today", "Yesterday", "This Week", "This Month", "Custom"],
        horizontal=True
    )

    today = pd.Timestamp.today().normalize()

    if filter_option == "Today":
        start_date = end_date = today

    elif filter_option == "Yesterday":
        start_date = end_date = today - pd.Timedelta(days=1)

    elif filter_option == "This Week":
        start_date = today - pd.Timedelta(days=today.weekday())
        end_date = today

    elif filter_option == "This Month":
        start_date = today.replace(day=1)
        end_date = today

    else:  # Custom
        col1, col2 = st.columns(2)
        with col1:
            start_date = pd.to_datetime(st.date_input("Start date", today))
        with col2:
            end_date = pd.to_datetime(st.date_input("End date", today))

    # ----------------------------
    # LOAD SALES DATA
    # ----------------------------
    conn = get_db()
    sales = pd.read_sql(
        """
        SELECT
            s.sale_id,
            s.product_id,
            p.brand,
            p.model,
            s.size,
            s.net_quantity AS quantity,
            s.net_revenue AS revenue,
            s.net_cost AS cost,
            s.sale_date,
            s.payment_method,
            s.paid_time,
            s.fulfillment_type,
            s.delivery_option,
            s.payment_cash_amount,
            s.payment_mpesa_amount,
            s.discount_type,
            s.discount_value,
            s.discount_amount,
            s.gross_revenue,
            s.notes
        FROM net_sales s
        JOIN products p ON p.id = s.product_id
        """,
        conn
    )

    if "notes" not in sales.columns:
        sales["notes"] = ""
    conn.close()
    
    if sales.empty:
        st.info("No sales data available.")
        return

    sales["sale_date"] = pd.to_datetime(sales["sale_date"])
    sales["revenue"] = pd.to_numeric(sales["revenue"], errors="coerce").fillna(0)
    sales["cost"] = pd.to_numeric(sales["cost"], errors="coerce").fillna(0)
    sales["gross_revenue"] = pd.to_numeric(sales["gross_revenue"], errors="coerce").fillna(0)
    sales["discount_value"] = pd.to_numeric(sales["discount_value"], errors="coerce").fillna(0)
    sales["discount_amount"] = pd.to_numeric(sales["discount_amount"], errors="coerce").fillna(0)
    sales["payment_cash_amount"] = pd.to_numeric(sales["payment_cash_amount"], errors="coerce").fillna(0)
    sales["payment_mpesa_amount"] = pd.to_numeric(sales["payment_mpesa_amount"], errors="coerce").fillna(0)

    # Apply date filter
    mask = (sales["sale_date"] >= start_date) & (sales["sale_date"] <= end_date)
    sales = sales.loc[mask]

    # Filter brokered sales if needed
    sales_type = st.selectbox(
        "Sales Type",
        ["All sales", "Regular only", "Brokered only"],
        key="sales_type_filter"
    )
    is_brokered = sales["notes"].str.contains("Brokered Sale", case=False, na=False)
    if sales_type == "Regular only":
        sales = sales.loc[~is_brokered]
    elif sales_type == "Brokered only":
        sales = sales.loc[is_brokered]

    if sales.empty:
        st.warning("No sales found for selected period.")
        return

    # ----------------------------
    # KPIs
    # ----------------------------
    total_revenue = int(sales["revenue"].sum())
    total_cost = int(sales["cost"].sum())
    profit = total_revenue - total_cost

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue (KES)", total_revenue)
    c2.metric("Cost (KES)", total_cost)
    c3.metric("Profit (KES)", profit)
    c4.metric("Units Sold", int(sales["quantity"].sum()))

    st.divider()

    # ----------------------------
    #  Revenue / Cost / Profit Trend
    # ----------------------------
    st.subheader("Revenue, Cost and Profit")

    trend = sales.groupby("sale_date")[["revenue", "cost"]].sum()
    trend["profit"] = trend["revenue"] - trend["cost"]
    st.line_chart(trend)

    st.divider()

    # ----------------------------
    #  Top Selling Products
    # ----------------------------
    st.subheader("Top Selling Products")

    top_df = (
        sales.groupby(["brand", "model"])["quantity"]
        .sum()
        .reset_index()
        .sort_values(by="quantity", ascending=False)
    )
    top_df["product"] = top_df["brand"] + " " + top_df["model"]

    st.bar_chart(top_df.set_index("product")[["quantity"]])

    st.divider()

    # ----------------------------
    #  Payment Breakdown
    # ----------------------------
    st.subheader("Revenue by Payment Method")
    payment = sales.groupby("payment_method")["revenue"].sum()
    st.bar_chart(payment)

    st.divider()

    # ----------------------------
    #  Detailed Sales Table
    # ----------------------------
    st.subheader("Detailed Sales")
    sales["type"] = sales["notes"].str.contains("Brokered Sale", case=False, na=False).map(
        lambda x: "Brokered" if x else "Regular"
    )
    st.dataframe(
        sales[
            [
                "product_id",
                "brand",
                "model",
                "size",
                "quantity",
                "gross_revenue",
                "discount_type",
                "discount_value",
                "discount_amount",
                "revenue",
                "cost",
                "payment_method",
                "payment_cash_amount",
                "payment_mpesa_amount",
                "paid_time",
                "fulfillment_type",
                "delivery_option",
                "type",
                "notes",
                "sale_date",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )

    st.divider()

    with st.expander("Export Sales Data", expanded=False):
        pdf_bytes = build_sales_analytics_pdf(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            sales_type=sales_type,
            total_revenue=total_revenue,
            total_cost=total_cost,
            total_profit=profit,
            total_units=int(sales["quantity"].sum()),
            trend_df=trend,
            top_df=top_df,
            payment_series=payment,
            detailed_df=sales,
        )
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=f"sales_analytics_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            key="sales_analytics_pdf_download",
        )

        #  CSV export (always available)
        csv = sales.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            data=csv,
            file_name="sales_report.csv",
            mime="text/csv",
        )

        #  Excel export (only if engine exists)
        try:
            from io import BytesIO
            excel_buffer = BytesIO()
            sales.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)

            st.download_button(
                "Download Excel",
                data=excel_buffer,
                file_name="sales_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception:
            st.info("Excel export not available on this system. Use CSV.")

def admin_monthly_activity_summary():
    st.subheader(" Monthly Activity Summary")

    # Month selector
    selected_month = st.date_input(
        "Select Month",
        value=pd.Timestamp.today(),
        help="Pick any date within the month you want to review"
    )

    start_date = pd.to_datetime(selected_month).replace(day=1)
    end_date = start_date + pd.offsets.MonthEnd(1)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")


    conn = get_db()

    # ----------------------------
    # SALES SUMMARY
    # ----------------------------
    sales = pd.read_sql(
        """
        SELECT
            (revenue * (quantity - COALESCE(returned_quantity, 0)) / quantity) AS revenue,
            (cost * (quantity - COALESCE(returned_quantity, 0)) / quantity) AS cost,
            (quantity - COALESCE(returned_quantity, 0)) AS quantity,
            sale_date
        FROM sales
        WHERE sale_date BETWEEN ? AND ?
        AND return_status != 'FULL'
        """,
        conn,
        params=(start_str, end_str)
    )

    sales["revenue"] = pd.to_numeric(sales["revenue"], errors="coerce").fillna(0)
    sales["cost"] = pd.to_numeric(sales["cost"], errors="coerce").fillna(0)

    total_revenue = int(sales["revenue"].sum())
    total_cost = int(sales["cost"].sum())
    profit = total_revenue - total_cost
    sales_count = int(sales["quantity"].sum())

    # ----------------------------
    # RETURNS & EXCHANGES
    # ----------------------------
    re = pd.read_sql(
        """
        SELECT
            re.type,
            re.status,
            re.created_at,
            s.sale_date
        FROM returns_exchanges re
        LEFT JOIN sales s ON s.id = re.sale_id
        WHERE (
            s.sale_date BETWEEN ? AND ?
        )
        OR (
            re.sale_id IS NULL
            AND date(re.created_at) BETWEEN ? AND ?
        )
        """,
        conn,
        params=(start_str, end_str, start_str, end_str)
    )

    approved_returns = len(re[(re["type"] == "RETURN") & (re["status"] == "APPROVED")])
    rejected_returns = len(re[(re["type"] == "RETURN") & (re["status"] == "REJECTED")])
    exchanges = len(re[re["type"] == "EXCHANGE"])

    # ----------------------------
    # ACTIVITY LOG
    # ----------------------------
    activity = pd.read_sql(
        """
        SELECT event_type, message, created_at
        FROM activity_log
        WHERE date(created_at) BETWEEN ? AND ?
        ORDER BY created_at DESC
        """,
        conn,
        params=(start_str, end_str)
    )

    conn.close()

    # ----------------------------
    # METRICS
    # ----------------------------
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue (KES)", total_revenue)
    c2.metric("Profit (KES)", profit)
    c3.metric("Sales Count", sales_count)
    c4.metric("Exchanges", exchanges)

    c5, c6 = st.columns(2)
    c5.metric("Returns Approved", approved_returns)
    c6.metric("Returns Rejected", rejected_returns)

    st.divider()

    # ----------------------------
    # ACTIVITY TIMELINE
    # ----------------------------
    st.subheader(" Activity Timeline")

    if activity.empty:
        st.info("No activity logged for this month.")
    else:
        for _, row in activity.iterrows():
            st.write(
                f" **{row['event_type']}**  {row['message']} "
                f"({row['created_at']})"
            )

# ----------------------------
# ACTIVITY LOG (ADMIN VIEW)
# ----------------------------
def admin_activity_log():
    st.subheader(" System Activity Log")

    conn = get_db()
    logs = pd.read_sql(
        """
        SELECT event_type, reference_id, role, username, message, created_at
        FROM activity_log
        ORDER BY created_at DESC
        LIMIT 200
        """,
        conn
    )
    conn.close()

    if logs.empty:
        st.info("No activity logged yet.")
        return

    # Friendly labels
    logs.rename(
        columns={
            "event_type": "Event",
            "reference_id": "Ref ID",
            "role": "Role",
            "username": "User",
            "message": "Details",
            "created_at": "Timestamp"
        },
        inplace=True
    )

    st.dataframe(
        logs,
        use_container_width=True,
        hide_index=True
    )


# ----------------------------
# PRODUCT WORKFLOW
# ----------------------------
def add_or_update_product_size(cur, product_id, size, quantity):
    cur.execute(
        """
        SELECT 1 FROM product_sizes
        WHERE product_id = ? AND size = ?
        """,
        (product_id, size)
    )

    exists = cur.fetchone()

    if exists:
        cur.execute(
            """
            UPDATE product_sizes
            SET quantity = ?
            WHERE product_id = ? AND size = ?
            """,
            (quantity, product_id, size)
        )
    else:
        cur.execute(
            """
            INSERT INTO product_sizes (product_id, size, quantity)
            VALUES (?, ?, ?)
            """,
            (product_id, size, quantity)
        )

def manager_manage_sizes():
    st.subheader(" Add / Update Product Sizes")

    conn = get_db()
    products = pd.read_sql(
        "SELECT id, brand, model, color, category FROM products",
        conn
)
    
    conn.close()

    if products.empty:
        st.info("No products available.")
        return

    product_id = st.selectbox(
        "Select Product",
        products["id"],
        format_func=lambda x: (
            products[products["id"] == x][
                ["brand", "model", "color"]
            ]
            .iloc[0]
            .to_string()
        )
    )

    product_row = products[products["id"] == product_id].iloc[0]
    category = product_row["category"].lower()
    if category == "women":
        allowed_sizes = [str(s) for s in range(35, 42)]  # 3541
    elif category == "men":
        allowed_sizes = [str(s) for s in range(40, 46)]  # 4045
    else:
        allowed_sizes = [str(s) for s in range(35, 46)]  # fallback

    size = st.selectbox(
        f"Size (Allowed: {allowed_sizes[0]}{allowed_sizes[-1]})",
        allowed_sizes,
        key=f"size_select_{product_id}"
    )

    quantity = st.number_input(
        "Quantity",
        min_value=0,
        step=1,
        key=f"manage_size_qty_{product_id}_{size}"
    )

    if st.button(" Save Size Stock"):
        conn = get_db()
        cur = conn.cursor()

        add_or_update_product_size(cur, product_id, size, quantity)

        sync_product_stock(cur, product_id)   #  pass SAME cursor

        conn.commit()
        conn.close()

        show_success_summary(
            "Size quantity updated.",
            [
                ("Product ID", int(product_id)),
                ("Size", str(size)),
                ("Quantity", int(quantity)),
            ],
        )

#reduce/adjust product stocks
def reduce_existing_product_stock(role):
    st.subheader(" Reduce Stock (Correction / Damage / Loss)")

    if role not in ["Admin", "Manager"]:
        st.error("Unauthorized")
        return

    conn = get_db()
    products = pd.read_sql(
        """
        SELECT id, brand, model, color, category
        FROM products
        WHERE is_active = 1
        ORDER BY brand, model
        """,
        conn
    )
    conn.close()

    if products.empty:
        st.info("No active products available.")
        return

    product_id = st.selectbox(
        "Select Product",
        products["id"],
        format_func=lambda x: (
            products[products["id"] == x][["brand", "model", "color"]]
            .iloc[0]
            .to_string()
        ),
        key=f"reduce_stock_product_{role}"
    )

    product = products[products["id"] == product_id].iloc[0]

    # Size logic
    if str(product["category"]).lower() == "women":
        allowed_sizes = [str(s) for s in range(35, 42)]
    else:
        allowed_sizes = [str(s) for s in range(40, 46)]

    size = st.selectbox(
        "Size",
        allowed_sizes,
        key=f"reduce_stock_size_{role}_{product_id}"
    )

    qty_to_reduce = st.number_input(
        "Quantity to Reduce",
        min_value=1,
        step=1,
        key=f"reduce_stock_qty_{role}_{product_id}_{size}"
    )

    reason = st.text_input(
        "Reason (required)",
        placeholder="e.g. damaged, lost, counting correction",
        key=f"reduce_stock_reason_{role}_{product_id}_{size}"
    )

    if st.button(" Confirm Reduce Stock", key=f"reduce_stock_submit_{role}_{product_id}_{size}"):

        if not reason.strip():
            st.error(" Reason is required for audit trail.")
            return

        conn = get_db()
        cur = conn.cursor()

        # 1 Check current size stock
        row = cur.execute(
            """
            SELECT quantity
            FROM product_sizes
            WHERE product_id = ? AND size = ?
            """,
            (int(product_id), str(size))
        ).fetchone()

        current_qty = int(row[0]) if row else 0

        # 2 Prevent negative stock
        if qty_to_reduce > current_qty:
            conn.close()
            st.error(f" Cannot reduce {qty_to_reduce}. Current stock for size {size} is {current_qty}.")
            return

        # 3 Reduce stock
        new_qty = current_qty - int(qty_to_reduce)

        add_or_update_product_size(
            cur,
            int(product_id),
            str(size),
            new_qty
        )

        # 4 Sync total stock
        sync_product_stock(cur, int(product_id))

        # 5 Audit trail
        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "STOCK_REDUCED",
                int(product_id),
                role,
                st.session_state.username,
                f"Reduced size {size}, Qty {qty_to_reduce}. Reason: {reason}"
            )
        )

        conn.commit()
        conn.close()

        show_success_summary(
            "Stock reduced successfully.",
            [
                ("Product ID", int(product_id)),
                ("Size", str(size)),
                ("Quantity Reduced", int(qty)),
            ],
        )
        st.rerun()

def admin_pending_buying_price():
    st.subheader(" Products Pending Buying Price")

    conn = get_db()
    df = pd.read_sql(
        "SELECT id, brand, model, color FROM products WHERE buying_price IS NULL",
        conn,
    )
    conn.close()

    if df.empty:
        st.success("No pending products ")
        return

    pid = st.selectbox(
        "Select Product",
        df["id"],
        format_func=lambda x: df[df["id"] == x][["brand", "model", "color"]].iloc[0].to_string(),
    )

    buying_price = st.number_input(
        "Buying Price (KES)",
        min_value=0,
        key=f"admin_buying_price_{pid}"
    )


    if st.button("Save Buying Price"):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE products SET buying_price= ? WHERE id= ?",
            (buying_price, pid),
        )
        conn.commit()
        conn.close()
        show_success_summary(
            "Buying price saved.",
            [
                ("Product ID", int(pid)),
                ("Buying Price (KES)", int(buying_price)),
            ],
        )

# ----------------------------
# STOCK MANAGEMENT (Admin & Manager)
#Update Restocked Products
def restock_existing_product(role):
    st.subheader(" Restock Existing Product")

    conn = get_db()
    products = pd.read_sql(
        """
        SELECT id, brand, model, color, category, buying_price
        FROM products
        WHERE is_active = 1
        ORDER BY brand, model
        """,
        conn
    )
    conn.close()

    if products.empty:
        st.info("No active products available.")
        return

    brands = sorted(products["brand"].fillna("").astype(str).unique().tolist())
    selected_brand = st.selectbox("Brand", brands, key=f"restock_brand_{role}")
    models_df = products[products["brand"] == selected_brand].copy()
    models = sorted(models_df["model"].fillna("").astype(str).unique().tolist())
    selected_model = st.selectbox("Model", models, key=f"restock_model_{role}")
    colors_df = models_df[models_df["model"] == selected_model].copy()
    colors = sorted(colors_df["color"].fillna("").astype(str).unique().tolist())
    selected_color = st.selectbox("Color", colors, key=f"restock_color_{role}")

    product = colors_df[colors_df["color"] == selected_color].iloc[0]
    product_id = int(product["id"])

    # Size logic: show full category range + any existing legacy/custom sizes.
    conn_sizes = get_db()
    existing_sizes_df = pd.read_sql(
        "SELECT size FROM product_sizes WHERE product_id = ? ORDER BY size",
        conn_sizes,
        params=(int(product_id),),
    )
    conn_sizes.close()
    existing_sizes = set(existing_sizes_df["size"].dropna().astype(str).tolist()) if not existing_sizes_df.empty else set()
    if str(product["category"]).strip().lower() == "women":
        category_sizes = {str(s) for s in range(35, 42)}
    else:
        category_sizes = {str(s) for s in range(40, 46)}
    allowed_sizes = sorted(existing_sizes.union(category_sizes), key=lambda x: (len(x), x))

    size = st.selectbox(
        "Size",
        allowed_sizes,
        key=f"restock_size_{role}_{product_id}"
    )

    quantity = st.number_input(
        "Quantity to Add",
        min_value=1,
        step=1,
        key=f"restock_qty_{role}_{product_id}_{size}"
    )

    # Buying price logic
    update_default_price = False
    if role == "Admin":
        unit_cost = st.number_input(
            "Buying Price per Unit (KES)",
            min_value=0,
            value=int(product["buying_price"] or 0),
            key=f"restock_cost_{role}_{product_id}"
        )
        update_default_price = st.checkbox(
            "Update product default buying price to this value",
            value=True,
            key=f"restock_update_default_{role}_{product_id}",
        )
    else:
        unit_cost = product["buying_price"]

    if st.button(" Confirm Restock", key=f"restock_submit_{role}_{product_id}_{size}"):

        conn = get_db()
        cur = conn.cursor()

        # 1 Add size stock
        row = cur.execute(
            """
            SELECT quantity
            FROM product_sizes
            WHERE product_id = ? AND size = ?
            """,
            (product_id, size)
        ).fetchone()

        existing_qty = row[0] if row else 0

        add_or_update_product_size(
            cur,
            product_id,
            size,
            existing_qty + quantity
        )

        if float(unit_cost or 0) <= 0:
            conn.close()
            st.error(" Unit cost must be greater than 0.")
            return

        # 2 Create a new cost layer (preserves old cost history)
        cur.execute(
            """
            INSERT INTO stock_cost_layers (product_id, size, remaining_qty, unit_cost, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            (int(product_id), str(size), int(quantity), float(unit_cost), f"RESTOCK_{role.upper()}"),
        )

        # 3 Optional default buying price update (Admin only)
        if role == "Admin" and update_default_price:
            cur.execute(
                "UPDATE products SET buying_price = ? WHERE id = ?",
                (unit_cost, product_id)
            )

        # 4 Sync total stock
        sync_product_stock(cur, product_id)

        # 5 Audit trail
        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "PRODUCT_RESTOCKED",
                product_id,
                role,
                st.session_state.username,
                f"Restocked size {size}, Qty {quantity}, Unit cost {unit_cost}"
            )
        )

        conn.commit()
        conn.close()

        show_success_summary(
            "Restock completed successfully.",
            [
                ("Product ID", int(product_id)),
                ("Size", str(size)),
                ("Quantity Added", int(quantity)),
            ],
        )
        st.rerun()

def stock_operations_panel(role):
    st.subheader(" Stock Operations")
    st.caption("Use this module for all stock-changing actions. Inventory is read-only.")

    op_mode = st.radio(
        "Choose operation",
        [
            "Add New Style (New Brand + Model + Color)",
            "Add New Model under Existing Brand",
            "Add New Color to Existing Brand + Model",
            "Restock Existing Brand + Model + Color",
        ],
        key=f"{role}_stock_operations_mode",
    )

    if op_mode == "Add New Style (New Brand + Model + Color)":
        st.session_state[f"{role}_add_mode"] = "New Style (Brand + Model)"
        add_product_and_sizes(role)
    elif op_mode == "Add New Model under Existing Brand":
        st.session_state[f"{role}_add_mode"] = "New Model under Existing Brand"
        add_product_and_sizes(role)
    elif op_mode == "Add New Color to Existing Brand + Model":
        st.session_state[f"{role}_add_mode"] = "New Color for Existing Style"
        add_product_and_sizes(role)
    else:
        restock_existing_product(role)

def add_product_and_sizes(role):
    st.subheader(" Add Product & Sizes")
    mode = st.radio(
        "What are you adding?",
        [
            "New Style (Brand + Model)",
            "New Model under Existing Brand",
            "New Color for Existing Style",
        ],
        horizontal=True,
        key=f"{role}_add_mode",
    )

    conn = get_db()
    existing_styles = pd.read_sql(
        """
        SELECT DISTINCT brand, model, category
        FROM products
        WHERE is_active = 1
          AND COALESCE(brand, '') <> ''
          AND COALESCE(model, '') <> ''
        ORDER BY brand, model
        """,
        conn,
    )
    conn.close()

    known_brands = sorted(
        existing_styles["brand"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()
    ) if not existing_styles.empty else []

    if mode == "New Style (Brand + Model)":
        category = st.selectbox("Category", ["Women", "Men"], key=f"{role}_new_style_category")
        brand = st.text_input("Brand", key=f"{role}_new_style_brand")
        model = st.text_input("Model", key=f"{role}_new_style_model")
        color = st.text_input("Color", key=f"{role}_new_style_color")
    elif mode == "New Model under Existing Brand":
        if not known_brands:
            st.warning("No existing brands found. Create a new style first.")
            return
        category = st.selectbox("Category", ["Women", "Men"], key=f"{role}_existing_brand_new_model_category")
        brand = st.selectbox("Brand", known_brands, key=f"{role}_existing_brand_pick")
        model = st.text_input("Model", key=f"{role}_existing_brand_new_model")
        color = st.text_input("Color", key=f"{role}_existing_brand_new_color")
    else:
        if existing_styles.empty:
            st.warning("No existing styles found. Create a new style first.")
            return
        existing_styles["style_display"] = existing_styles["brand"] + " | " + existing_styles["model"]
        style_choice = st.selectbox(
            "Select Existing Style",
            existing_styles["style_display"].tolist(),
            key=f"{role}_existing_style_choice",
        )
        selected_style = existing_styles[existing_styles["style_display"] == style_choice].iloc[0]
        brand = str(selected_style["brand"])
        model = str(selected_style["model"])
        category = str(selected_style["category"] or "Women")
        st.caption(f"Selected style: {brand} {model} | Category: {category}")
        color = st.text_input("New Color", key=f"{role}_existing_style_new_color")

    selling_price = st.number_input(
    "Selling Price (KES)",
    min_value=0,
    key=f"{role}_new_product_selling_price"
    )

    if role == "Admin":
        buying_price = st.number_input(
            "Buying Price (KES)",
            min_value=0,
            key=f"{role}_new_product_buying_price"
        )
    else:
        buying_price = None
        st.caption("Admin will add buying price.")

    # ----------------------------
    # SIZE INPUTS (REQUIRED)
    # ----------------------------
    st.markdown("###  Sizes & Initial Stock")

    sizes = {}
    allowed_sizes = (
        range(35, 42) if category == "Women" else range(40, 46)
    )

    for size in allowed_sizes:
        qty = st.number_input(
            f"Size {size}",
            min_value=0,
            key=f"{role}_new_product_size_{size}"
        )
        if qty > 0:
            sizes[str(size)] = qty
    # ----------------------------
    # SAVE
    # ----------------------------
    if st.button(" Save Product"):
        if not brand or not model or not color:
            st.error(" All product fields are required.")
            return

        if not sizes:
            st.error(" You must add at least one size.")
            return

        conn = get_db()
        cur = conn.cursor()

        try:
            conn.execute("BEGIN")

            dup = cur.execute(
                """
                SELECT id
                FROM products
                WHERE LOWER(TRIM(COALESCE(brand, ''))) = LOWER(TRIM(?))
                  AND LOWER(TRIM(COALESCE(model, ''))) = LOWER(TRIM(?))
                  AND LOWER(TRIM(COALESCE(color, ''))) = LOWER(TRIM(?))
                  AND COALESCE(is_active, 1) = 1
                LIMIT 1
                """,
                (brand, model, color),
            ).fetchone()
            if dup:
                conn.rollback()
                st.error("This style/color already exists. Use Restock instead.")
                conn.close()
                return

            cur.execute(
                """
                INSERT INTO products
                (category, brand, model, color,
                 buying_price, selling_price, stock)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    category,
                    brand,
                    model,
                    color,
                    buying_price,
                    selling_price,
                )
            )

            product_id = cur.lastrowid

            for size, qty in sizes.items():
                cur.execute(
                    """
                    INSERT INTO product_sizes
                    (product_id, size, quantity)
                    VALUES (?, ?, ?)
                    """,
                    (product_id, size, qty)
                )

            sync_product_stock(cur, product_id)

            conn.commit()

            show_success_summary(
                "Product created successfully.",
                [
                    ("Product ID", int(product_id)),
                    ("Brand", str(brand)),
                    ("Model", str(model)),
                    ("Color", str(color)),
                ],
            )

        except Exception as e:
            conn.rollback()
            st.error(f" Failed to save product: {e}")

        finally:
            conn.close()

#Pending Return Requests
def admin_handle_returns():
    st.subheader(" Pending Return Requests")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            r.id AS request_id,
            r.sale_id,
            r.size,
            r.quantity AS return_qty,
            COALESCE(r.refund_amount, 0) AS refund_amount,
            COALESCE(r.refund_method, '') AS refund_method,
            r.notes,
            r.initiated_by,
            p.id AS product_id,
            p.brand,
            p.model,
            p.color,
            s.quantity AS sold_qty,
            s.revenue,
            s.return_status,
            COALESCE(s.returned_quantity, 0) AS already_returned
        FROM returns_exchanges r
        JOIN sales s ON s.id = r.sale_id
        JOIN products p ON p.id = s.product_id
        WHERE r.type = 'RETURN'
        AND r.status = 'PENDING'
        AND s.return_status != 'FULL'
        ORDER BY r.created_at ASC
        """,
        conn
    )
    conn.close()
    if df.empty:
        st.success("No pending return requests ")
        return

    # ----------------------------
    # Select request
    # ----------------------------
    request_id = st.selectbox(
        "Select Return Request",
        df["request_id"],
        format_func=lambda x: (
            df[df["request_id"] == x][
                ["brand", "model", "color", "size", "return_qty", "initiated_by"]
            ]
            .iloc[0]
            .to_string()
        )
    )

    row = df[df["request_id"] == request_id].iloc[0]

    st.info(
        f"""
        **Product:** {row['brand']} {row['model']} ({row['color']})  
        **Size:** {row['size']}  
        **Quantity to return:** {row['return_qty']}  
        **Refund Amount:** KES {int(row['refund_amount'])}  
        **Refund Method:** {row['refund_method'] or 'Not specified'}  
        **Requested by:** {row['initiated_by']}
        """
    )

    admin_note = st.text_area(
        " Admin Notes",
        placeholder="Reason for approval or rejection"
    )

    col1, col2 = st.columns(2)

    # ----------------------------
    # APPROVE
    # ----------------------------
    with col1:
        if st.button(" Approve Return"):
            # Validate return quantity exists
            if row["return_qty"] is None or row["return_qty"] <= 0:
                st.error(" Invalid return quantity")
                return
                
            conn = get_db()
            cur = conn.cursor()
            
            # 1 Check current sale status
            # 1 Check current sale status
            cur.execute(
                """
                SELECT quantity, COALESCE(returned_quantity, 0), return_status
                FROM sales
                WHERE id = ?
                """,
                (int(row["sale_id"]),)
            )

            result = cur.fetchone()

            if not result:
                st.error(f" Original sale record not found. Sale ID: {row['sale_id']}")
                conn.close()
                return

            # Force type conversion to integers
            sold_qty = int(result[0]) if result[0] is not None else 0
            already_returned = int(result[1]) if result[1] is not None else 0
            current_status = result[2] if result[2] is not None else 'NONE'

            # Account for other pending return requests on the same sale
            cur.execute("""
                SELECT COALESCE(SUM(quantity), 0)
                FROM returns_exchanges
                WHERE sale_id = ?
                  AND type = 'RETURN'
                  AND status = 'PENDING'
                  AND id != ?
            """, (int(row["sale_id"]), int(request_id)))
            pending_other = int(cur.fetchone()[0] or 0)

            st.write(
                f" Sale Check: Sold={sold_qty}, Already Returned={already_returned}, "
                f"Pending Other={pending_other}, Status={current_status}"
            )

            # 2 Prevent over-return
            if row["return_qty"] + already_returned + pending_other > sold_qty:
                st.error(
                    f" Cannot approve return. "
                    f"Attempting to return {row['return_qty']}, "
                    f"but only {sold_qty - already_returned - pending_other} item(s) remain returnable."
                )
                conn.close()
                return

            # 3 Update sales table - THIS IS CRITICAL
            new_returned_qty = already_returned + row["return_qty"]
            new_status = 'FULL' if new_returned_qty >= sold_qty else 'PARTIAL'
            
            cur.execute(
                """
                UPDATE sales
                SET
                    returned_quantity = ?,
                    return_status = ?
                WHERE id = ?
                """,
                (new_returned_qty, new_status, int(row["sale_id"]))
            )
            
            # Verify the update worked
            rows_updated = cur.rowcount
            st.write(f" Sales table updated: {rows_updated} row(s)")

            # 4 Restore stock to product_sizes
            cur.execute("""
            INSERT INTO product_sizes (product_id, size, quantity)
            VALUES (?, ?, 0)
            ON CONFLICT(product_id, size) DO NOTHING
            """, (int(row["product_id"]), str(row["size"])))

            cur.execute("""
            UPDATE product_sizes
            SET quantity = quantity + ?
            WHERE product_id = ? AND size = ?
            """, (
                int(row["return_qty"]),
                int(row["product_id"]),
                str(row["size"])
            ))

            # 5 Sync main product stock
            sync_product_stock(cur, row["product_id"])

            # 6 Mark return as approved
            cur.execute(
                """
                UPDATE returns_exchanges
                SET status = 'APPROVED',
                    approved_by = ?,
                    notes = COALESCE(notes, '') || ' | ADMIN: ' || ?
                WHERE id = ?
                """,
                (st.session_state.username, admin_note, int(request_id))
            )

            # 7 Activity log
            cur.execute(
                """
                INSERT INTO activity_log
                (event_type, reference_id, role, username, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "RETURN_APPROVED",
                    int(request_id),
                    "Admin",
                    st.session_state.username,
                    (
                        f"Approved return  Sale ID {row['sale_id']}, Size {row['size']}, "
                        f"Qty {row['return_qty']}, Refund KES {int(row['refund_amount'])} via "
                        f"{row['refund_method'] or 'Not specified'}. {admin_note}"
                    )
                )
            )
            
            conn.commit()
            conn.close()

            show_success_summary(
                "Return approved successfully.",
                [
                    ("Sale ID", int(row["sale_id"])),
                    ("Size", str(row["size"])),
                    ("Quantity", int(row["return_qty"])),
                    ("Refund (KES)", int(row["refund_amount"] or 0)),
                    ("Refund Method", str(row["refund_method"] or "Not specified")),
                ],
            )
            time.sleep(1)
            st.rerun()
    # ----------------------------
    # REJECT
    # ----------------------------
    with col2:
        if st.button(" Reject Return"):
            conn = get_db()
            cur = conn.cursor()

            cur.execute(
                """
                UPDATE returns_exchanges
                SET status = 'REJECTED',
                    notes = notes || ' | ADMIN: ' || ?
                WHERE id = ?
                """,
                (admin_note, request_id)
            )

            cur.execute(
                """
                INSERT INTO activity_log
                (event_type, reference_id, role, username, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "RETURN_REJECTED",
                    request_id,
                    "Admin",
                    st.session_state.username,
                    (
                        f"Rejected return  Size {row['size']}, Qty {row['return_qty']}, "
                        f"Requested refund KES {int(row['refund_amount'])} via "
                        f"{row['refund_method'] or 'Not specified'}. {admin_note}"
                    )
                )
            )

            conn.commit()
            conn.close()

            st.warning(" Return rejected")
            st.rerun()

def handle_admin_return_action(request_id, decision, admin_note):
    conn = get_db()
    cur = conn.cursor()

    # Update return request status
    cur.execute(
        """
        UPDATE returns_exchanges
        SET status = ?
        WHERE id = ?
        """,
        (decision, request_id)
    )

    # Log admin activity
    cur.execute(
        """
        INSERT INTO activity_log
        (event_type, reference_id, role, username, message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            f"RETURN_{decision}",
            request_id,
            "Admin",
            st.session_state.username,
            admin_note
        )
    )

    conn.commit()
    conn.close()

    show_success_summary(
        f"Return request {decision.lower()} successfully.",
        [
            ("Request ID", int(request_id)),
            ("Status", decision.upper()),
        ],
    )
    st.rerun()

#Returns and updates on sales history
def upgrade_sales_for_returns():
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("ALTER TABLE sales ADD COLUMN returned_quantity INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cur.execute("ALTER TABLE sales ADD COLUMN return_status TEXT DEFAULT 'NONE'")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return int(default)


def _validate_backdate_request_date(request_type, payload):
    field_map = {
        "BACKDATE_SALE": "sale_date",
        "BACKDATE_EXPENSE": "expense_date",
        "BACKDATE_STOCK": "stock_date",
    }
    field = field_map.get(str(request_type), "")
    if not field:
        return False, f"Unsupported request type: {request_type}"

    raw_value = str(payload.get(field, "")).strip()
    if not raw_value:
        return False, f"Missing {field}."

    try:
        effective_date = pd.to_datetime(raw_value, errors="raise").date()
    except Exception:
        return False, f"Invalid {field}: {raw_value}"

    if effective_date >= pd.Timestamp.today().date():
        return False, f"{field} must be before today."

    return True, ""


def _sync_product_stock_for_id(cur, product_id):
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
        (int(product_id), int(product_id)),
    )


def _apply_approved_backdate_request(cur, request_type, payload):
    if request_type == "BACKDATE_SALE":
        sale_type = str(payload.get("sale_type", "Regular Sale"))
        quantity = _safe_int(payload.get("quantity"), 1)
        revenue = _safe_int(payload.get("revenue"), 0)
        cost = _safe_int(payload.get("cost"), 0)
        payment_method = str(payload.get("payment_method", "CASH"))
        source = str(payload.get("source", "Other"))
        sale_date = str(payload.get("sale_date", ""))
        sale_time = str(payload.get("sale_time", payload.get("paid_time", "00:00:00")))
        paid_time = str(payload.get("paid_time", sale_time))
        fulfillment_type = str(payload.get("fulfillment_type", "In-store Pickup"))
        delivery_option = str(payload.get("delivery_option", ""))
        delivery_location = str(payload.get("delivery_location", ""))
        payment_cash_amount = float(payload.get("payment_cash_amount", 0) or 0)
        payment_mpesa_amount = float(payload.get("payment_mpesa_amount", 0) or 0)
        discount_type = str(payload.get("discount_type", "None"))
        discount_value = float(payload.get("discount_value", 0) or 0)
        discount_amount = float(payload.get("discount_amount", 0) or 0)
        gross_revenue = float(payload.get("gross_revenue", revenue) or revenue)
        customer_session_id = str(payload.get("customer_session_id", "") or "")
        if not customer_session_id:
            customer_session_id = generate_customer_session_id()
        customer_count_unit = _safe_int(payload.get("customer_count_unit"), 1)
        if customer_count_unit not in (0, 1):
            customer_count_unit = 1
        notes = str(payload.get("notes", ""))

        if sale_type == "Brokered Sale (Profit Only)":
            brokered_product_id = get_or_create_brokered_product()
            broker_category = str(payload.get("broker_category", "")).strip()
            broker_brand = str(payload.get("broker_brand", "")).strip()
            broker_model = str(payload.get("broker_model", "")).strip()
            broker_color = str(payload.get("broker_color", "")).strip()
            broker_size = str(payload.get("broker_size", "")).strip() or "N/A"
            broker_identity = (
                f"{broker_category} | {broker_brand} {broker_model} {broker_color} | "
                f"Size {broker_size}"
            ).strip()
            if notes.strip():
                final_notes = notes.strip()
                if not final_notes.lower().startswith("brokered sale"):
                    final_notes = f"Brokered Sale | {final_notes}"
            elif broker_identity:
                final_notes = f"Brokered Sale | {broker_identity}"
            else:
                final_notes = "Brokered Sale"
            cur.execute(
                """
                INSERT INTO sales
                (product_id, size, quantity, revenue, cost, payment_method, source, sale_date, sale_time, paid_time, fulfillment_type, delivery_option, delivery_location, payment_cash_amount, payment_mpesa_amount, discount_type, discount_value, discount_amount, gross_revenue, customer_session_id, customer_count_unit, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(brokered_product_id),
                    broker_size,
                    int(quantity),
                    int(revenue),
                    int(cost),
                    payment_method,
                    source,
                    sale_date,
                    sale_time,
                    paid_time,
                    fulfillment_type,
                    delivery_option,
                    delivery_location,
                    payment_cash_amount,
                    payment_mpesa_amount,
                    discount_type,
                    discount_value,
                    discount_amount,
                    gross_revenue,
                    customer_session_id,
                    int(customer_count_unit),
                    final_notes,
                ),
            )
            return int(cur.lastrowid)

        product_id = _safe_int(payload.get("product_id"), 0)
        size = str(payload.get("size", ""))
        if product_id <= 0 or not size:
            raise ValueError("Invalid sale payload: missing product/size.")

        cur.execute(
            """
            INSERT INTO sales
            (product_id, size, quantity, revenue, cost, payment_method, source, sale_date, sale_time, paid_time, fulfillment_type, delivery_option, delivery_location, payment_cash_amount, payment_mpesa_amount, discount_type, discount_value, discount_amount, gross_revenue, customer_session_id, customer_count_unit, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(product_id),
                size,
                int(quantity),
                int(revenue),
                int(cost),
                payment_method,
                source,
                sale_date,
                sale_time,
                paid_time,
                fulfillment_type,
                delivery_option,
                delivery_location,
                payment_cash_amount,
                payment_mpesa_amount,
                discount_type,
                discount_value,
                discount_amount,
                gross_revenue,
                customer_session_id,
                int(customer_count_unit),
                notes,
            ),
        )
        sale_id = int(cur.lastrowid)
        cur.execute(
            """
            UPDATE product_sizes
            SET quantity = quantity - ?
            WHERE product_id = ? AND size = ?
            """,
            (int(quantity), int(product_id), size),
        )
        _sync_product_stock_for_id(cur, product_id)
        return sale_id

    if request_type == "BACKDATE_EXPENSE":
        amount = _safe_int(payload.get("amount"), 0)
        description = str(payload.get("description", "")).strip()
        expense_category = str(payload.get("expense_category", "Other")).strip() or "Other"
        expense_date = str(payload.get("expense_date", ""))
        if amount <= 0 or not description:
            raise ValueError("Invalid expense payload.")
        cur.execute(
            """
            INSERT INTO operating_expenses (expense_date, category, description, amount)
            VALUES (?, ?, ?, ?)
            """,
            (expense_date, expense_category, description, int(amount)),
        )
        return int(cur.lastrowid)

    if request_type == "BACKDATE_STOCK":
        product_id = _safe_int(payload.get("product_id"), 0)
        size = str(payload.get("size", "")).strip()
        quantity = _safe_int(payload.get("quantity"), 0)
        if product_id <= 0 or quantity <= 0 or not size:
            raise ValueError("Invalid stock payload.")
        cur.execute(
            """
            INSERT INTO product_sizes (product_id, size, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(product_id, size)
            DO UPDATE SET quantity = quantity + ?
            """,
            (int(product_id), size, int(quantity), int(quantity)),
        )
        _sync_product_stock_for_id(cur, product_id)
        return int(product_id)

    raise ValueError(f"Unsupported request type: {request_type}")


def _handle_backdate_request_decision(request_id, decision, admin_note):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, request_type, payload_json, status, requested_by
            FROM backdate_approval_requests
            WHERE id = ?
            """,
            (int(request_id),),
        )
        row = cur.fetchone()
        if not row:
            return False, "Request not found."
        if row["status"] != "PENDING":
            return False, f"Request already {row['status']}."

        if decision == "REJECTED":
            cur.execute(
                """
                UPDATE backdate_approval_requests
                SET status = 'REJECTED',
                    approved_by = ?,
                    admin_note = ?,
                    decided_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (st.session_state.username, admin_note, int(request_id)),
            )
            cur.execute(
                """
                INSERT INTO activity_log (event_type, reference_id, role, username, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "BACKDATE_REQUEST_REJECTED",
                    int(request_id),
                    "Admin",
                    st.session_state.username,
                    f"Rejected {row['request_type']} request #{request_id}. Admin action at: {now_nairobi_str()}. Note: {admin_note}",
                ),
            )
            conn.commit()
            return True, "Request rejected."

        payload = json.loads(row["payload_json"] or "{}")
        valid, validation_msg = _validate_backdate_request_date(row["request_type"], payload)
        if not valid:
            cur.execute(
                """
                UPDATE backdate_approval_requests
                SET status = 'REJECTED',
                    approved_by = ?,
                    admin_note = ?,
                    error_message = ?,
                    decided_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    st.session_state.username,
                    f"Rejected by server-side validation. {admin_note}".strip(),
                    validation_msg,
                    int(request_id),
                ),
            )
            cur.execute(
                """
                INSERT INTO activity_log (event_type, reference_id, role, username, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "BACKDATE_REQUEST_REJECTED",
                    int(request_id),
                    "Admin",
                    st.session_state.username,
                    f"Rejected {row['request_type']} request #{request_id}. Validation failed: {validation_msg}",
                ),
            )
            conn.commit()
            return False, f"Request rejected by system validation: {validation_msg}"

        effective_date = (
            payload.get("expense_date")
            or payload.get("sale_date")
            or payload.get("stock_date")
            or "N/A"
        )
        applied_reference_id = _apply_approved_backdate_request(cur, row["request_type"], payload)
        cur.execute(
            """
            UPDATE backdate_approval_requests
            SET status = 'APPROVED',
                approved_by = ?,
                admin_note = ?,
                applied_reference_id = ?,
                decided_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                st.session_state.username,
                admin_note,
                int(applied_reference_id) if applied_reference_id is not None else None,
                int(request_id),
            ),
        )
        cur.execute(
            """
            INSERT INTO activity_log (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "BACKDATE_REQUEST_APPROVED",
                int(request_id),
                "Admin",
                st.session_state.username,
                f"Approved {row['request_type']} request #{request_id}. Effective date: {effective_date}. Applied ref #{applied_reference_id}. Admin action at: {now_nairobi_str()}",
            ),
        )
        conn.commit()
        return True, "Request approved and applied."
    except Exception as e:
        conn.rollback()
        try:
            cur.execute(
                """
                UPDATE backdate_approval_requests
                SET error_message = ?
                WHERE id = ?
                """,
                (str(e), int(request_id)),
            )
            conn.commit()
        except Exception:
            pass
        return False, f"Error processing request: {e}"
    finally:
        conn.close()


def admin_handle_backdate_approvals():
    st.subheader(" Backdate Approval Queue")
    conn = get_db()
    pending = pd.read_sql(
        """
        SELECT id, request_type, requested_by, requested_role, created_at, payload_json
        FROM backdate_approval_requests
        WHERE status = 'PENDING'
        ORDER BY created_at DESC, id DESC
        """,
        conn,
    )
    conn.close()

    if pending.empty:
        st.success("No pending backdate approval requests.")
        return

    for _, row in pending.iterrows():
        request_id = int(row["id"])
        request_type = str(row["request_type"])
        payload = {}
        try:
            payload = json.loads(row.get("payload_json") or "{}")
        except Exception:
            payload = {}

        title = (
            f"#{request_id} - {request_type} - by {row.get('requested_by', 'unknown')} "
            f"({row.get('requested_role', 'unknown')}) - {row.get('created_at', '')}"
        )
        with st.expander(title, expanded=False):
            st.json(payload)
            admin_note = st.text_input(
                "Admin Note",
                key=f"backdate_admin_note_{request_id}",
                placeholder="Reason for approval or rejection",
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Approve and Apply", key=f"approve_backdate_{request_id}", use_container_width=True):
                    ok, msg = _handle_backdate_request_decision(request_id, "APPROVED", admin_note)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    st.error(msg)
            with c2:
                if st.button("Reject Request", key=f"reject_backdate_{request_id}", use_container_width=True):
                    ok, msg = _handle_backdate_request_decision(request_id, "REJECTED", admin_note)
                    if ok:
                        st.warning(msg)
                        st.rerun()
                    st.error(msg)


def admin_view_activity_log():
    st.subheader(" System Activity Log")
    st.markdown("#### Activity Period")
    period = st.radio(
        "Select Period",
        ["This Month", "Last Month", "Custom"],
        horizontal=True,
        key="activity_log_period",
        label_visibility="collapsed",
    )
    today = datetime.now().date()
    if period == "This Month":
        start_date = today.replace(day=1)
        end_date = today
    elif period == "Last Month":
        first_this = today.replace(day=1)
        end_last = first_this - timedelta(days=1)
        start_date = end_last.replace(day=1)
        end_date = end_last
    else:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("From date", value=today.replace(day=1), key="activity_log_start")
        with col2:
            end_date = st.date_input("To date", value=today, key="activity_log_end")
        if start_date > end_date:
            st.error("From date cannot be after To date.")
            return

    if st.button("Load Activity Log", key="activity_log_load"):
        st.session_state["activity_log_loaded"] = True

    if not st.session_state.get("activity_log_loaded", False):
        render_theme_notice("Select period and click Load Activity Log.")
        return

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT event_type, reference_id, role, username, message, created_at
        FROM activity_log
        WHERE date(created_at) BETWEEN date(?) AND date(?)
        ORDER BY created_at DESC
        """,
        conn,
        params=(start_date.isoformat(), end_date.isoformat()),
    )
    conn.close()

    if df.empty:
        st.warning("No activity matches the selected period.")
        return

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", format="mixed")

    col1, col2 = st.columns(2)
    with col1:
        users = ["All"] + sorted(df["username"].dropna().unique().tolist())
        selected_user = st.selectbox("User", users, key="activity_log_user")
    with col2:
        event_types = ["All"] + sorted(df["event_type"].unique().tolist())
        selected_event = st.selectbox("Event Type", event_types, key="activity_log_event")

    mask = pd.Series(True, index=df.index)
    if selected_user != "All":
        mask &= df["username"] == selected_user
    if selected_event != "All":
        mask &= df["event_type"] == selected_event

    filtered = df.loc[mask]
    if filtered.empty:
        st.warning("No activity matches the selected filters.")
        return

    st.dataframe(filtered, use_container_width=True, hide_index=True)

def admin_data_integrity_panel():
    st.subheader("Data Integrity")
    issues = count_integrity_issues()

    c1, c2 = st.columns(2)
    c1.metric("Stock Mismatch Rows", issues["stock_mismatch"])
    c2.metric("Negative Size Rows", issues["negative_size_rows"])

    c3, c4 = st.columns(2)
    c3.metric("Regular Sales with Zero Cost", issues["zero_cost_regular"])
    c4.metric("Missing Operating Expense Logs", issues["missing_operating_logs"])

    c5, _ = st.columns(2)
    c5.metric("Missing Home Expense Logs", issues["missing_home_logs"])

    if st.button("Re-sync Product Stock Totals"):
        updated = sync_all_product_stock()
        st.success(f"Stock totals re-synced for {updated} products.")
        st.rerun()

    if st.button("Backfill Missing Expense Activity Logs"):
        op_inserted, home_inserted = backfill_missing_expense_logs()
        st.success(f"Inserted {op_inserted} operating and {home_inserted} home expense log entries.")
        st.rerun()

    if st.button("Backfill Fixable Zero-Cost Regular Sales"):
        updated = backfill_fixable_zero_cost_sales()
        st.success(f"Updated {updated} regular sales using current product buying prices.")
        st.caption("Brokered sales are intentionally excluded from this fix.")
        st.rerun()
#Admin archive or restore products
def admin_archive_restore_product():
    st.subheader(" Archive / Restore Products")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT id, brand, model, color, is_active
        FROM products
        ORDER BY brand, model
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.info("No products available.")
        return

    pid = st.selectbox(
        "Select Product",
        df["id"],
        format_func=lambda x: (
            df[df["id"] == x][["brand", "model", "color"]]
            .iloc[0]
            .to_string()
        )
    )

    row = df[df["id"] == pid].iloc[0]
    is_active = int(row["is_active"])

    if is_active == 1:
        st.success(" This product is ACTIVE")
        action = st.button(" Archive Product")
    else:
        st.warning(" This product is ARCHIVED")
        action = st.button(" Restore Product")

    if action:
        conn = get_db()
        cur = conn.cursor()

        new_state = 0 if is_active == 1 else 1
        event = "PRODUCT_ARCHIVED" if new_state == 0 else "PRODUCT_RESTORED"

        cur.execute(
            "UPDATE products SET is_active= ? WHERE id= ?",
            (new_state, pid)
        )

        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event,
                pid,
                "Admin",
                st.session_state.username,
                f"{event.replace('_', ' ').title()}"
            )
        )

        conn.commit()
        conn.close()

        show_success_summary(
            "Product status updated successfully.",
            [
                ("Product ID", int(product_id)),
                ("Status", new_status),
            ],
        )
        st.rerun()

def _get_exchangeable_qty(conn, sale_id):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COALESCE(quantity, 0), COALESCE(returned_quantity, 0)
        FROM sales
        WHERE id = ?
        """,
        (int(sale_id),),
    )
    row = cur.fetchone()
    if not row:
        return 0
    sold_qty = int(row[0] or 0)
    returned_qty = int(row[1] or 0)
    cur.execute(
        """
        SELECT COALESCE(SUM(quantity), 0)
        FROM returns_exchanges
        WHERE sale_id = ?
          AND type = 'RETURN'
          AND status = 'PENDING'
        """,
        (int(sale_id),),
    )
    pending_returns = int(cur.fetchone()[0] or 0)
    cur.execute(
        """
        SELECT COALESCE(SUM(quantity), 0)
        FROM returns_exchanges
        WHERE sale_id = ?
          AND type = 'EXCHANGE'
          AND status IN ('PENDING', 'APPROVED')
        """,
        (int(sale_id),),
    )
    used_exchange_qty = int(cur.fetchone()[0] or 0)
    return max(sold_qty - returned_qty - pending_returns - used_exchange_qty, 0)

def _get_exchangeability_breakdown(conn, sale_id):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COALESCE(quantity, 0), COALESCE(returned_quantity, 0)
        FROM sales
        WHERE id = ?
        """,
        (int(sale_id),),
    )
    row = cur.fetchone()
    if not row:
        return {"sold_qty": 0, "returned_qty": 0, "pending_returns": 0, "used_exchange_qty": 0, "available": 0}
    sold_qty = int(row[0] or 0)
    returned_qty = int(row[1] or 0)
    cur.execute(
        """
        SELECT COALESCE(SUM(quantity), 0)
        FROM returns_exchanges
        WHERE sale_id = ?
          AND type = 'RETURN'
          AND status = 'PENDING'
        """,
        (int(sale_id),),
    )
    pending_returns = int(cur.fetchone()[0] or 0)
    cur.execute(
        """
        SELECT COALESCE(SUM(quantity), 0)
        FROM returns_exchanges
        WHERE sale_id = ?
          AND type = 'EXCHANGE'
          AND status IN ('PENDING', 'APPROVED')
        """,
        (int(sale_id),),
    )
    used_exchange_qty = int(cur.fetchone()[0] or 0)
    available = max(sold_qty - returned_qty - pending_returns - used_exchange_qty, 0)
    return {
        "sold_qty": sold_qty,
        "returned_qty": returned_qty,
        "pending_returns": pending_returns,
        "used_exchange_qty": used_exchange_qty,
        "available": available,
    }


def _load_active_exchange_products(conn):
    df = pd.read_sql(
        """
        SELECT id, brand, model, color, selling_price
        FROM products
        WHERE is_active = 1
          AND NOT (
              LOWER(TRIM(COALESCE(category, ''))) = 'external'
              AND LOWER(TRIM(COALESCE(brand, ''))) = 'brokered'
              AND LOWER(TRIM(COALESCE(model, ''))) = 'brokered sale'
          )
        ORDER BY brand, model, color
        """,
        conn,
    )
    if df.empty:
        return df
    df["brand"] = df["brand"].fillna("").astype(str)
    df["model"] = df["model"].fillna("").astype(str)
    df["color"] = df["color"].fillna("").astype(str)
    df["display"] = df["brand"] + " " + df["model"] + " (" + df["color"] + ")"
    return df


def _load_product_sizes(conn, product_id):
    return pd.read_sql(
        """
        SELECT size, quantity
        FROM product_sizes
        WHERE product_id = ?
          AND quantity > 0
        ORDER BY size
        """,
        conn,
        params=(int(product_id),),
    )


def _apply_exchange_stock_transaction(conn, payload):
    cur = conn.cursor()
    from_product_id = int(payload["from_product_id"])
    from_size = str(payload["from_size"])
    exchange_qty = int(payload["exchange_qty"])
    to_items = payload.get("to_items", [])
    if exchange_qty <= 0 or not to_items:
        raise ValueError("Invalid exchange payload.")

    for item in to_items:
        pid = int(item["product_id"])
        size = str(item["size"])
        qty = int(item["quantity"])
        if qty <= 0:
            raise ValueError("Replacement quantity must be greater than 0.")
        cur.execute(
            """
            SELECT COALESCE(quantity, 0)
            FROM product_sizes
            WHERE product_id = ? AND size = ?
            """,
            (pid, size),
        )
        row = cur.fetchone()
        if not row or int(row[0]) < qty:
            raise ValueError(f"Insufficient stock for replacement item (Product {pid}, Size {size}).")

    touched_products = {from_product_id}
    cur.execute(
        """
        INSERT INTO product_sizes (product_id, size, quantity)
        VALUES (?, ?, 0)
        ON CONFLICT(product_id, size) DO NOTHING
        """,
        (from_product_id, from_size),
    )
    cur.execute(
        """
        UPDATE product_sizes
        SET quantity = quantity + ?
        WHERE product_id = ? AND size = ?
        """,
        (exchange_qty, from_product_id, from_size),
    )

    for item in to_items:
        pid = int(item["product_id"])
        size = str(item["size"])
        qty = int(item["quantity"])
        touched_products.add(pid)
        cur.execute(
            """
            UPDATE product_sizes
            SET quantity = quantity - ?
            WHERE product_id = ? AND size = ?
            """,
            (qty, pid, size),
        )
        if cur.rowcount <= 0:
            raise ValueError(f"Failed to deduct replacement stock for product {pid}, size {size}.")

    for pid in touched_products:
        sync_product_stock(cur, int(pid))


def _insert_exchange_record(conn, payload, status, initiated_by, approved_by=None, admin_note=""):
    cur = conn.cursor()
    settlement_amount = float(abs(payload.get("difference_value", 0)))
    cur.execute(
        """
        INSERT INTO returns_exchanges
        (sale_id, type, size, quantity, amount, settlement_direction, settlement_amount, settlement_method,
         exchange_mode, exchange_payload, notes, initiated_by, status, approved_by)
        VALUES (?, 'EXCHANGE', ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(payload["sale_id"]),
            str(payload.get("from_size", "")),
            int(payload["exchange_qty"]),
            str(payload.get("settlement_direction", "NONE")),
            float(settlement_amount),
            str(payload.get("settlement_method", "")),
            str(payload.get("exchange_mode", "PRODUCT_EXCHANGE")),
            json.dumps(payload),
            str(admin_note or payload.get("notes", "")).strip(),
            str(initiated_by),
            str(status),
            str(approved_by or ""),
        ),
    )
    return int(cur.lastrowid)


# returns_exchanges exchange center
def manager_process_exchange():
    role = str(st.session_state.get("role", "Unknown"))
    is_admin = role == "Admin"
    st.subheader("Exchange Center")
    if is_admin:
        st.caption("Admin can process exchanges immediately. Cashier/Manager requests require admin approval.")
    else:
        st.caption("Submit exchange requests for admin approval.")

    conn = get_db()
    sales = pd.read_sql(
        """
        SELECT
            s.sale_id,
            COALESCE(s.sale_date, '') AS sale_date,
            s.product_id,
            COALESCE(s.size, 'N/A') AS sold_size,
            COALESCE(s.net_quantity, 0) AS quantity,
            COALESCE(s.net_revenue, 0) AS revenue,
            COALESCE(p.brand, 'Unknown') AS brand,
            COALESCE(p.model, 'Unknown') AS model,
            COALESCE(p.color, '') AS color
        FROM net_sales s
        JOIN products p ON p.id = s.product_id
        WHERE COALESCE(s.net_quantity, 0) > 0
        ORDER BY s.sale_id DESC
        """,
        conn,
    )
    if sales.empty:
        st.info("No sales available for exchange.")
        conn.close()
        return

    sales = sales.copy()
    sales["sale_label"] = sales.apply(
        lambda r: (
            f"Sale #{int(r['sale_id'])} | {str(r.get('sale_date', 'N/A'))} | "
            f"{str(r['brand'])} {str(r['model'])} | Color {str(r['color'])} | "
            f"Size {str(r['sold_size'])} | Qty {int(r['quantity'])} | "
            f"Revenue KES {int(r['revenue'])}"
        ),
        axis=1,
    )
    sale_options = dict(zip(sales["sale_label"], sales["sale_id"]))
    sale_placeholder = "Select original sale"
    sale_select_options = [sale_placeholder] + list(sale_options.keys())
    selected_sale_label = st.selectbox(
        "Select Original Sale",
        sale_select_options,
        key="exchange_sale_id_label",
    )
    if selected_sale_label == sale_placeholder:
        render_theme_notice("Select the original sale to continue.")
        conn.close()
        return

    sale_id = int(sale_options[selected_sale_label])
    sale = sales[sales["sale_id"] == sale_id].iloc[0]
    from_product_id = int(sale["product_id"])
    from_size = str(sale["sold_size"])
    exchangeable_qty = _get_exchangeable_qty(conn, int(sale_id))
    if exchangeable_qty <= 0:
        st.warning("No exchangeable quantity is available for this sale.")
        parts = _get_exchangeability_breakdown(conn, int(sale_id))
        st.caption(
            "Availability check: "
            f"Sold={parts['sold_qty']}, Returned={parts['returned_qty']}, "
            f"Pending Returns={parts['pending_returns']}, Used Exchange Qty={parts['used_exchange_qty']}, "
            f"Available={parts['available']}."
        )
        conn.close()
        return

    exchange_mode_placeholder = "Select exchange type"
    exchange_mode_label = st.selectbox(
        "Exchange Type",
        [exchange_mode_placeholder] + [
            "Size Exchange (Same Product)",
            "Product Exchange (Different Product)",
            "Value Exchange (Top-up/Balance)",
        ],
        key="exchange_mode_label",
    )
    if exchange_mode_label == exchange_mode_placeholder:
        render_theme_notice("Select exchange type to continue.")
        conn.close()
        return

    exchange_mode = {
        "Size Exchange (Same Product)": "SIZE_EXCHANGE",
        "Product Exchange (Different Product)": "PRODUCT_EXCHANGE",
        "Value Exchange (Top-up/Balance)": "VALUE_EXCHANGE",
    }[exchange_mode_label]

    qty_placeholder = "Select quantity"
    qty_options = [qty_placeholder] + [int(i) for i in range(1, int(exchangeable_qty) + 1)]
    qty_selected = st.selectbox(
        "Quantity to Exchange (returned from original sale)",
        qty_options,
        key="exchange_qty_select",
    )
    if qty_selected == qty_placeholder:
        render_theme_notice("Select quantity to continue.")
        conn.close()
        return
    exchange_qty = int(qty_selected)

    unit_price = 0.0
    if int(sale["quantity"] or 0) > 0:
        unit_price = float(sale["revenue"] or 0) / float(sale["quantity"] or 1)
    original_value = round(float(unit_price) * int(exchange_qty), 2)
    st.info(
        f"Original line: {sale['brand']} {sale['model']} ({sale['color']}) | "
        f"Size {from_size} | Exchangeable Qty {exchangeable_qty} | "
        f"Exchange Value KES {int(original_value)}"
    )

    products_df = _load_active_exchange_products(conn)
    if products_df.empty:
        st.error("No active products available for replacement.")
        conn.close()
        return
    product_map = dict(zip(products_df["display"], products_df["id"]))

    to_items = []

    def collect_replacement_line(prefix, default_qty):
        product_label = st.selectbox(
            f"Replacement Product ({prefix})",
            list(product_map.keys()),
            key=f"exchange_{prefix}_product",
        )
        pid = int(product_map[product_label])
        size_df = _load_product_sizes(conn, pid)
        if size_df.empty:
            st.warning(f"No in-stock sizes for {product_label}.")
            return None
        size = st.selectbox(
            f"Replacement Size ({prefix})",
            size_df["size"].astype(str).tolist(),
            key=f"exchange_{prefix}_size",
        )
        stock_row = size_df[size_df["size"].astype(str) == str(size)]
        in_stock = int(stock_row["quantity"].iloc[0]) if not stock_row.empty else 0
        qty = st.number_input(
            f"Replacement Qty ({prefix})",
            min_value=1,
            max_value=max(in_stock, 1),
            value=min(max(default_qty, 1), max(in_stock, 1)),
            step=1,
            key=f"exchange_{prefix}_qty",
        )
        product_row = products_df[products_df["id"] == pid].iloc[0]
        unit_sell = float(product_row.get("selling_price") or 0)
        return {
            "product_id": int(pid),
            "size": str(size),
            "quantity": int(qty),
            "unit_price": float(unit_sell),
            "label": str(product_label),
        }

    if exchange_mode == "SIZE_EXCHANGE":
        same_sizes_df = _load_product_sizes(conn, from_product_id)
        same_sizes_df = same_sizes_df[same_sizes_df["size"].astype(str) != from_size]
        if same_sizes_df.empty:
            st.warning("No alternate in-stock sizes on this product.")
            conn.close()
            return
        new_size = st.selectbox(
            "Replacement Size",
            same_sizes_df["size"].astype(str).tolist(),
            key="exchange_same_size_to",
        )
        to_items = [{
            "product_id": int(from_product_id),
            "size": str(new_size),
            "quantity": int(exchange_qty),
            "unit_price": float(unit_price),
            "label": f"{sale['brand']} {sale['model']} ({sale['color']})",
        }]
    elif exchange_mode == "PRODUCT_EXCHANGE":
        line = collect_replacement_line("single", int(exchange_qty))
        if line:
            if int(line["product_id"]) == int(from_product_id) and str(line["size"]) == str(from_size):
                st.error("Replacement cannot be exactly the same product and size.")
                conn.close()
                return
            to_items = [line]
    else:
        line_count = st.number_input(
            "Number of Replacement Lines",
            min_value=1,
            max_value=4,
            value=2,
            step=1,
            key="exchange_multi_lines",
        )
        for i in range(int(line_count)):
            line = collect_replacement_line(f"line_{i+1}", 1)
            if line:
                to_items.append(line)

    replacement_value = round(sum(float(item["unit_price"]) * int(item["quantity"]) for item in to_items), 2)
    difference_value = round(replacement_value - original_value, 2)
    if difference_value > 0:
        settlement_direction = "TOPUP"
        settlement_text = f"Customer tops up KES {int(difference_value)}"
    elif difference_value < 0:
        settlement_direction = "REFUND"
        settlement_text = f"Refund customer KES {int(abs(difference_value))}"
    else:
        settlement_direction = "NONE"
        settlement_text = "No settlement difference"
    st.caption(
        f"Replacement value: KES {int(replacement_value)} | "
        f"Original exchange value: KES {int(original_value)} | "
        f"Settlement: {settlement_text}"
    )

    settlement_method = ""
    if settlement_direction == "TOPUP":
        settlement_method = st.selectbox("Top-up Method", ["Cash", "Mobile Money"], key="exchange_topup_method")
    elif settlement_direction == "REFUND":
        settlement_method = st.selectbox("Refund Method", ["Cash", "Mobile Money"], key="exchange_refund_method")

    notes = st.text_area("Exchange Notes", key="exchange_notes")
    action_label = "Process Exchange Now" if is_admin else "Submit Exchange Request"
    if st.button(action_label, key="exchange_submit_btn"):
        if not to_items:
            st.error("Add at least one replacement line.")
            conn.close()
            return

        payload = {
            "sale_id": int(sale_id),
            "exchange_mode": str(exchange_mode),
            "from_product_id": int(from_product_id),
            "from_size": str(from_size),
            "exchange_qty": int(exchange_qty),
            "original_unit_price": float(unit_price),
            "original_value": float(original_value),
            "to_items": to_items,
            "replacement_value": float(replacement_value),
            "difference_value": float(difference_value),
            "settlement_direction": str(settlement_direction),
            "settlement_method": str(settlement_method),
            "notes": str(notes or "").strip(),
        }

        cur = conn.cursor()
        try:
            if is_admin:
                _apply_exchange_stock_transaction(conn, payload)
                req_id = _insert_exchange_record(
                    conn=conn,
                    payload=payload,
                    status="APPROVED",
                    initiated_by=st.session_state.get("username", "admin"),
                    approved_by=st.session_state.get("username", "admin"),
                    admin_note=str(notes or "").strip(),
                )
                cur.execute(
                    """
                    INSERT INTO activity_log
                    (event_type, reference_id, role, username, message)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "EXCHANGE_APPROVED",
                        int(req_id),
                        "Admin",
                        st.session_state.get("username", "admin"),
                        (
                            f"Immediate exchange approved for sale {int(sale_id)}. "
                            f"Mode={exchange_mode}, Qty={int(exchange_qty)}, Settlement={settlement_direction} "
                            f"KES {int(abs(difference_value))} via {settlement_method or 'N/A'}."
                        ),
                    ),
                )
                conn.commit()
                show_success_summary(
                    "Exchange processed immediately.",
                    [
                        ("Sale ID", int(sale_id)),
                        ("Mode", exchange_mode),
                        ("Quantity", int(exchange_qty)),
                        ("Settlement", f"{settlement_direction} KES {int(abs(difference_value))}"),
                    ],
                )
            else:
                req_id = _insert_exchange_record(
                    conn=conn,
                    payload=payload,
                    status="PENDING",
                    initiated_by=st.session_state.get("username", "unknown"),
                    approved_by=None,
                    admin_note=str(notes or "").strip(),
                )
                cur.execute(
                    """
                    INSERT INTO activity_log
                    (event_type, reference_id, role, username, message)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "EXCHANGE_REQUESTED",
                        int(req_id),
                        st.session_state.get("role", "Unknown"),
                        st.session_state.get("username", "unknown"),
                        (
                            f"Exchange request for sale {int(sale_id)}. Mode={exchange_mode}, Qty={int(exchange_qty)}, "
                            f"Settlement={settlement_direction} KES {int(abs(difference_value))} via {settlement_method or 'N/A'}."
                        ),
                    ),
                )
                conn.commit()
                show_success_summary(
                    "Exchange request submitted for admin approval.",
                    [
                        ("Request ID", f"#{int(req_id)}"),
                        ("Sale ID", int(sale_id)),
                        ("Mode", exchange_mode),
                        ("Quantity", int(exchange_qty)),
                    ],
                )
            st.rerun()
        except Exception as exc:
            conn.rollback()
            st.error(f"Exchange could not be processed: {exc}")
        finally:
            conn.close()

    conn.close()


def admin_handle_exchange_requests():
    st.subheader("Pending Exchange Requests")
    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            re.id AS request_id,
            re.sale_id,
            COALESCE(re.exchange_mode, 'PRODUCT_EXCHANGE') AS exchange_mode,
            re.quantity,
            COALESCE(re.settlement_direction, 'NONE') AS settlement_direction,
            COALESCE(re.settlement_amount, 0) AS settlement_amount,
            COALESCE(re.settlement_method, '') AS settlement_method,
            re.initiated_by,
            re.status,
            re.exchange_payload,
            re.notes,
            re.created_at
        FROM returns_exchanges re
        WHERE re.type = 'EXCHANGE'
          AND re.status IN ('PENDING', 'IN_REVIEW')
        ORDER BY re.created_at ASC
        """,
        conn,
    )
    if df.empty:
        st.success("No pending exchange requests.")
        conn.close()
        return

    show = df.drop(columns=["exchange_payload"])
    st.dataframe(show, hide_index=True, use_container_width=True)

    request_id = st.selectbox("Select Exchange Request", df["request_id"], key="admin_exchange_request_id")
    row = df[df["request_id"] == request_id].iloc[0]
    payload = {}
    try:
        payload = json.loads(str(row["exchange_payload"] or "{}"))
    except Exception:
        payload = {}

    st.markdown(
        f"""
        **Sale ID:** {int(row['sale_id'])}  
        **Mode:** {row['exchange_mode']}  
        **Qty:** {int(row['quantity'])}  
        **Requested by:** {row['initiated_by']}  
        **Settlement:** {row['settlement_direction']} KES {int(float(row['settlement_amount'] or 0))} via {row['settlement_method'] or 'N/A'}  
        """
    )
    original_line = {}
    try:
        from_pid = int(payload.get("from_product_id") or 0)
        from_size = str(payload.get("from_size") or "")
        ex_qty = int(payload.get("exchange_qty") or 0)
        if from_pid > 0:
            p_row = pd.read_sql(
                """
                SELECT COALESCE(brand, 'Unknown') AS brand, COALESCE(model, 'Unknown') AS model, COALESCE(color, '') AS color
                FROM products
                WHERE id = ?
                """,
                conn,
                params=(from_pid,),
            )
            if not p_row.empty:
                original_line = {
                    "Type": "Original (Customer Returned)",
                    "Product": f"{p_row.iloc[0]['brand']} {p_row.iloc[0]['model']}",
                    "Color": str(p_row.iloc[0]["color"]),
                    "Size": from_size,
                    "Qty": ex_qty,
                    "Value (KES)": int(float(payload.get("original_value") or 0)),
                }
    except Exception:
        original_line = {}

    replacement_lines = []
    for item in payload.get("to_items", []) or []:
        try:
            pid = int(item.get("product_id") or 0)
            size = str(item.get("size") or "")
            qty = int(item.get("quantity") or 0)
            label = str(item.get("label") or "").strip()
            if pid > 0:
                p_row = pd.read_sql(
                    """
                    SELECT COALESCE(brand, 'Unknown') AS brand, COALESCE(model, 'Unknown') AS model, COALESCE(color, '') AS color
                    FROM products
                    WHERE id = ?
                    """,
                    conn,
                    params=(pid,),
                )
                if not p_row.empty:
                    label = f"{p_row.iloc[0]['brand']} {p_row.iloc[0]['model']}"
                    color = str(p_row.iloc[0]["color"])
                else:
                    color = ""
            else:
                color = ""
            replacement_lines.append(
                {
                    "Type": "Requested Replacement",
                    "Product": label,
                    "Color": color,
                    "Size": size,
                    "Qty": qty,
                    "Value (KES)": int(float(item.get("unit_price") or 0) * int(qty or 0)),
                }
            )
        except Exception:
            continue

    st.markdown("**Exchange Preview**")
    preview_rows = []
    if original_line:
        preview_rows.append(original_line)
    preview_rows.extend(replacement_lines)
    if preview_rows:
        st.dataframe(pd.DataFrame(preview_rows), hide_index=True, use_container_width=True)

    items = payload.get("to_items", [])
    if items:
        items_df = pd.DataFrame(items)
        if not items_df.empty:
            st.dataframe(items_df, hide_index=True, use_container_width=True)

    admin_note = st.text_area("Admin Note", key="admin_exchange_note")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Mark In Review", key="admin_exchange_in_review", use_container_width=True):
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE returns_exchanges
                SET status = 'IN_REVIEW',
                    approved_by = ?,
                    notes = COALESCE(notes, '') || ' | ADMIN: ' || ?
                WHERE id = ?
                """,
                (st.session_state.get("username", "admin"), str(admin_note or "").strip(), int(request_id)),
            )
            cur.execute(
                """
                INSERT INTO activity_log
                (event_type, reference_id, role, username, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "EXCHANGE_IN_REVIEW",
                    int(request_id),
                    "Admin",
                    st.session_state.get("username", "admin"),
                    f"Exchange request #{int(request_id)} moved to IN_REVIEW.",
                ),
            )
            conn.commit()
            show_success_summary(
                "Exchange request marked IN_REVIEW.",
                [("Request ID", int(request_id)), ("Status", "IN_REVIEW")],
            )
            st.rerun()
    with c2:
        if st.button("Approve Exchange", key="admin_exchange_approve", use_container_width=True):
            try:
                _apply_exchange_stock_transaction(conn, payload)
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE returns_exchanges
                    SET status = 'APPROVED',
                        approved_by = ?,
                        notes = COALESCE(notes, '') || ' | ADMIN: ' || ?
                    WHERE id = ?
                    """,
                    (st.session_state.get("username", "admin"), str(admin_note or "").strip(), int(request_id)),
                )
                cur.execute(
                    """
                    INSERT INTO activity_log
                    (event_type, reference_id, role, username, message)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "EXCHANGE_APPROVED",
                        int(request_id),
                        "Admin",
                        st.session_state.get("username", "admin"),
                        f"Approved exchange request #{int(request_id)}.",
                    ),
                )
                conn.commit()
                show_success_summary(
                    "Exchange approved and applied.",
                    [("Request ID", int(request_id)), ("Status", "APPROVED")],
                )
                st.rerun()
            except Exception as exc:
                conn.rollback()
                st.error(f"Unable to approve exchange: {exc}")
    with c3:
        if st.button("Reject Exchange", key="admin_exchange_reject", use_container_width=True):
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE returns_exchanges
                SET status = 'REJECTED',
                    approved_by = ?,
                    notes = COALESCE(notes, '') || ' | ADMIN: ' || ?
                WHERE id = ?
                """,
                (st.session_state.get("username", "admin"), str(admin_note or "").strip(), int(request_id)),
            )
            cur.execute(
                """
                INSERT INTO activity_log
                (event_type, reference_id, role, username, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "EXCHANGE_REJECTED",
                    int(request_id),
                    "Admin",
                    st.session_state.get("username", "admin"),
                    f"Rejected exchange request #{int(request_id)}.",
                ),
            )
            conn.commit()
            st.warning("Exchange request rejected.")
            st.rerun()
    conn.close()

def manager_view_admin_updates():
    st.subheader(" Admin Updates")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT event_type, message, created_at
        FROM activity_log
        WHERE role = 'Admin'
          AND event_type IN (
              'RETURN_APPROVED',
              'RETURN_REJECTED',
              'EXCHANGE_IN_REVIEW',
              'EXCHANGE_APPROVED',
              'EXCHANGE_REJECTED'
          )
        ORDER BY created_at DESC
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.info("No updates from admin yet.")
        return

    df["created_at"] = pd.to_datetime(df["created_at"])

    for _, row in df.iterrows():
        if row["event_type"] == "RETURN_APPROVED":
            st.success(
                f" Return approved\n\n"
                f"{row['message']}\n\n"
                f" {row['created_at']}"
            )

        elif row["event_type"] == "RETURN_REJECTED":
            st.error(
                f" Return rejected\n\n"
                f"{row['message']}\n\n"
                f" {row['created_at']}"
            )

        else:
            st.info(
                f" Exchange update\n\n"
                f"{row['message']}\n\n"
                f" {row['created_at']}"
            )

def manager_view_my_requests():
    st.subheader(" My Exchange Requests Status")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            re.id AS request_id,
            re.type,
            re.status,
            re.notes,
            re.created_at,
            al.message AS admin_message,
            al.created_at AS reviewed_at
        FROM returns_exchanges re
        LEFT JOIN activity_log al
            ON al.reference_id = re.id
            AND al.event_type IN ('RETURN_APPROVED', 'RETURN_REJECTED', 'EXCHANGE_IN_REVIEW', 'EXCHANGE_APPROVED', 'EXCHANGE_REJECTED')
        WHERE re.initiated_by = ?
          AND re.type = 'EXCHANGE'
        ORDER BY re.created_at DESC
        """,
        conn,
        params=(st.session_state.username,)
    )
    conn.close()

    if df.empty:
        st.info("No exchange requests yet.")
        return

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["reviewed_at"] = pd.to_datetime(df["reviewed_at"], errors="coerce")
    df = df.dropna(subset=["created_at"]).copy()
    if df.empty:
        st.info("No exchange requests yet.")
        return

    st.markdown("#### Request Period")
    period = st.radio(
        "Select Period",
        ["This Month", "Last Month", "Custom"],
        horizontal=True,
        key="manager_exchange_status_period",
        label_visibility="collapsed",
    )
    today = datetime.now().date()
    if period == "This Month":
        start_date = today.replace(day=1)
        end_date = today
    elif period == "Last Month":
        first_this = today.replace(day=1)
        end_last = first_this - timedelta(days=1)
        start_date = end_last.replace(day=1)
        end_date = end_last
    else:
        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Start date", value=today.replace(day=1), key="manager_exchange_status_start")
        with c2:
            end_date = st.date_input("End date", value=today, key="manager_exchange_status_end")
        if start_date > end_date:
            st.error("Start date cannot be after end date.")
            return

    df = df[(df["created_at"].dt.date >= start_date) & (df["created_at"].dt.date <= end_date)].copy()
    if df.empty:
        st.info("No exchange requests in the selected period.")
        return

    df = df.rename(columns={
        "type": "Request Type",
        "status": "Status",
        "notes": "Your Notes",
        "admin_message": "Admin Decision Notes",
        "created_at": "Requested At",
        "reviewed_at": "Reviewed At"
    })

    st.dataframe(
        df[
            [
                "Request Type",
                "Status",
                "Your Notes",
                "Admin Decision Notes",
                "Requested At",
                "Reviewed At",
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

def submit_sale_review_request_widget():
    st.subheader("Request Sale Review")
    st.caption("Use this when a sale was captured with a wrong price, quantity, payment mode, or other issue.")

    conn = get_db()
    sales_df = pd.read_sql(
        """
        SELECT
            s.id AS sale_id,
            s.sale_date,
            COALESCE(p.brand, 'Unknown') AS brand,
            COALESCE(p.model, 'Unknown') AS model,
            COALESCE(p.color, '') AS color,
            COALESCE(s.size, 'N/A') AS size,
            COALESCE(s.quantity, 0) AS quantity,
            COALESCE(s.revenue, 0) AS revenue,
            COALESCE(s.payment_method, '') AS payment_method
        FROM sales s
        LEFT JOIN products p ON p.id = s.product_id
        ORDER BY s.id DESC
        LIMIT 150
        """,
        conn,
    )
    conn.close()

    if sales_df.empty:
        st.info("No sales available to review.")
        return

    issue_type_placeholder = "-- Select issue type --"
    issue_type = st.selectbox(
        "Issue Type",
        [issue_type_placeholder] + [
            "Wrong Selling Price",
            "Wrong Quantity",
            "Wrong Payment Mode",
            "Wrong Size",
            "Wrong Product",
            "Other",
        ],
        key="sale_review_issue_type",
    )
    sale_options = ["-- Select sale --"] + sales_df["sale_id"].astype(str).tolist()
    if st.session_state.get("sale_review_sale_id") not in sale_options:
        st.session_state["sale_review_sale_id"] = "-- Select sale --"
    selected_sale_id = st.selectbox(
        "Select Sale",
        sale_options,
        format_func=lambda x: (
            x
            if x == "-- Select sale --"
            else (
                sales_df[sales_df["sale_id"] == int(x)][
                    ["sale_date", "brand", "model", "size", "quantity", "revenue", "payment_method"]
                ]
                .iloc[0]
                .to_string()
            )
        ),
        key="sale_review_sale_id",
    )
    expected_value = st.text_input(
        "Expected Correct Value",
        placeholder="Example: Selling price should be 2500, not 2000",
        key="sale_review_expected_value",
    )
    notes = st.text_area(
        "Notes",
        placeholder="Explain what happened and any supporting detail.",
        key="sale_review_notes",
    )

    if st.button("Submit Review Request", key="sale_review_submit"):
        if issue_type == issue_type_placeholder:
            st.error("Please select an issue type.")
            return
        if selected_sale_id == "-- Select sale --":
            st.error("Please select a sale to review.")
            return
        if not str(notes or "").strip():
            st.error("Please provide notes for admin review.")
            return

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO sale_review_requests
            (sale_id, issue_type, expected_value, notes, requested_by, requested_role, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'PENDING', CURRENT_TIMESTAMP)
            """,
            (
                int(selected_sale_id),
                str(issue_type),
                str(expected_value or "").strip(),
                str(notes).strip(),
                st.session_state.get("username", "unknown"),
                st.session_state.get("role", "Unknown"),
            ),
        )
        request_id = int(cur.lastrowid)
        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "SALE_REVIEW_REQUESTED",
                request_id,
                st.session_state.get("role", "Unknown"),
                st.session_state.get("username", "unknown"),
                f"Review requested for Sale ID {int(selected_sale_id)}. Issue: {issue_type}. Expected: {str(expected_value or '').strip()}",
            ),
        )
        conn.commit()
        conn.close()
        st.session_state["sale_review_issue_type"] = issue_type_placeholder
        st.session_state["sale_review_sale_id"] = "-- Select sale --"
        st.session_state["sale_review_expected_value"] = ""
        st.session_state["sale_review_notes"] = ""
        show_success_summary(
            "Review request submitted.",
            [
                ("Request ID", int(request_id)),
                ("Issue Type", str(issue_type)),
                ("Sale ID", int(selected_sale_id)),
            ],
        )
        st.rerun()

def my_sale_review_requests():
    st.subheader("My Sale Review Requests")
    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            id AS request_id,
            sale_id,
            issue_type,
            expected_value,
            status,
            admin_note,
            created_at,
            updated_at
        FROM sale_review_requests
        WHERE requested_by = ?
        ORDER BY id DESC
        LIMIT 50
        """,
        conn,
        params=(st.session_state.get("username", ""),),
    )
    conn.close()

    if df.empty:
        st.info("No sale review requests submitted yet.")
        return

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df.dropna(subset=["created_at"]).copy()
    if df.empty:
        st.info("No sale review requests submitted yet.")
        return

    st.markdown("#### Request Period")
    period = st.radio(
        "Select Period",
        ["This Month", "Last Month", "Custom"],
        horizontal=True,
        key="my_sale_review_period",
        label_visibility="collapsed",
    )
    today = datetime.now().date()
    if period == "This Month":
        start_date = today.replace(day=1)
        end_date = today
    elif period == "Last Month":
        first_this = today.replace(day=1)
        end_last = first_this - timedelta(days=1)
        start_date = end_last.replace(day=1)
        end_date = end_last
    else:
        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Start date", value=today.replace(day=1), key="my_sale_review_start")
        with c2:
            end_date = st.date_input("End date", value=today, key="my_sale_review_end")
        if start_date > end_date:
            st.error("Start date cannot be after end date.")
            return

    df = df[(df["created_at"].dt.date >= start_date) & (df["created_at"].dt.date <= end_date)].copy()
    if df.empty:
        render_theme_notice("No sale review requests in the selected period.")
        return

    st.dataframe(df, use_container_width=True, hide_index=True)

def render_review_sale_section():
    st.divider()
    with st.expander("Review a Sale", expanded=False):
        if st.session_state.get("role") == "Admin":
            st.info("Use Audit and Admin -> Sale Review Requests to process submitted requests.")
        else:
            submit_sale_review_request_widget()
            st.divider()
            my_sale_review_requests()

def admin_handle_sale_review_requests():
    st.subheader("Sale Review Requests")

    st.markdown("#### Request Period")
    sr_period = st.radio(
        "Select Period",
        ["This Month", "Last Month", "Custom"],
        horizontal=True,
        key="sale_review_admin_period",
        label_visibility="collapsed",
    )
    today = datetime.now().date()
    if sr_period == "This Month":
        start_date = today.replace(day=1)
        end_date = today
    elif sr_period == "Last Month":
        first_this = today.replace(day=1)
        end_last = first_this - timedelta(days=1)
        start_date = end_last.replace(day=1)
        end_date = end_last
    else:
        d1, d2 = st.columns(2)
        with d1:
            start_date = st.date_input("Start date", value=today.replace(day=1), key="sale_review_admin_start")
        with d2:
            end_date = st.date_input("End date", value=today, key="sale_review_admin_end")
        if start_date > end_date:
            st.error("Start date cannot be after end date.")
            return

    if st.button("Load Sale Review Requests", key="sale_review_admin_load"):
        st.session_state["sale_review_admin_loaded"] = True

    if not st.session_state.get("sale_review_admin_loaded", False):
        render_theme_notice("Select period and click Load Sale Review Requests.")
        return

    conn = get_db()
    pending_df = pd.read_sql(
        """
        SELECT
            r.id AS request_id,
            r.sale_id,
            r.issue_type,
            r.expected_value,
            r.notes,
            r.requested_by,
            r.requested_role,
            r.status,
            r.created_at,
            COALESCE(p.brand, 'Unknown') AS brand,
            COALESCE(p.model, 'Unknown') AS model,
            COALESCE(s.size, 'N/A') AS size,
            COALESCE(s.quantity, 0) AS quantity,
            COALESCE(s.revenue, 0) AS revenue,
            COALESCE(s.payment_method, '') AS payment_method
        FROM sale_review_requests r
        LEFT JOIN sales s ON s.id = r.sale_id
        LEFT JOIN products p ON p.id = s.product_id
        WHERE r.status IN ('PENDING', 'IN_REVIEW')
          AND date(r.created_at) BETWEEN date(?) AND date(?)
        ORDER BY r.id DESC
        """,
        conn,
        params=(start_date.isoformat(), end_date.isoformat()),
    )

    history_df = pd.read_sql(
        """
        SELECT
            id AS request_id,
            sale_id,
            issue_type,
            requested_by,
            status,
            admin_note,
            resolved_by,
            created_at,
            updated_at
        FROM sale_review_requests
        WHERE date(created_at) BETWEEN date(?) AND date(?)
        ORDER BY id DESC
        LIMIT 240
        """,
        conn,
        params=(start_date.isoformat(), end_date.isoformat()),
    )

    if pending_df.empty:
        st.success("No pending sale review requests.")
    else:
        st.dataframe(
            pending_df[
                [
                    "request_id",
                    "sale_id",
                    "issue_type",
                    "requested_by",
                    "requested_role",
                    "status",
                    "created_at",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        default_request_label = "-- Select request --"
        request_label_to_id = {}
        request_options = [default_request_label]
        for _, r in pending_df.iterrows():
            label = (
                f"Request #{int(r['request_id'])} | Sale #{int(r['sale_id'])} | "
                f"{r['issue_type']} | by {r['requested_by']} | status {r['status']}"
            )
            request_label_to_id[label] = int(r["request_id"])
            request_options.append(label)

        existing_sel = st.session_state.get("sale_review_admin_selected")
        if isinstance(existing_sel, str) and existing_sel.isdigit():
            existing_id = int(existing_sel)
            for label, rid in request_label_to_id.items():
                if rid == existing_id:
                    st.session_state["sale_review_admin_selected"] = label
                    break
            else:
                st.session_state["sale_review_admin_selected"] = default_request_label
        elif existing_sel not in request_options:
            st.session_state["sale_review_admin_selected"] = default_request_label

        selected_request_label = st.selectbox(
            "Select Request to Process",
            request_options,
            key="sale_review_admin_selected",
        )

        selected_request_id = request_label_to_id.get(selected_request_label)
        if selected_request_id is None:
            st.info("Select a request to view details and action buttons.")
            row = None
        else:
            row = pending_df[pending_df["request_id"] == int(selected_request_id)].iloc[0]
        if row is None:
            st.markdown("### Recent Sale Review Requests")
            if history_df.empty:
                st.info("No sale review history yet.")
            else:
                st.dataframe(history_df, use_container_width=True, hide_index=True)
            conn.close()
            return
        st.markdown(
            f"""
            **Request ID:** {int(row['request_id'])}  
            **Sale ID:** {int(row['sale_id'])}  
            **Product:** {row['brand']} {row['model']}  
            **Size / Qty:** {row['size']} / {int(row['quantity'])}  
            **Recorded Revenue:** KES {int(row['revenue'])}  
            **Payment:** {row['payment_method']}  
            **Issue:** {row['issue_type']}  
            **Expected:** {row['expected_value']}  
            **Requested By:** {row['requested_by']} ({row['requested_role']})  
            **User Notes:** {row['notes']}  
            """
        )

        admin_note = st.text_area(
            "Admin Note",
            placeholder="State decision and required correction steps.",
            key="sale_review_admin_note",
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Mark In Review", key="sale_review_mark_in_review", use_container_width=True):
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE sale_review_requests
                    SET status = 'IN_REVIEW',
                        admin_note = ?,
                        resolved_by = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        str(admin_note or "").strip(),
                        st.session_state.get("username", "admin"),
                        int(selected_request_id),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO activity_log
                    (event_type, reference_id, role, username, message)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "SALE_REVIEW_IN_REVIEW",
                        int(selected_request_id),
                        "Admin",
                        st.session_state.get("username", "admin"),
                        f"Sale review request {int(selected_request_id)} marked IN_REVIEW.",
                    ),
                )
                conn.commit()
                st.session_state["sale_review_admin_selected"] = default_request_label
                st.session_state["sale_review_admin_note"] = ""
                show_success_summary(
                    "Request moved to IN_REVIEW.",
                    [
                        ("Request ID", int(selected_request_id)),
                        ("Status", "IN_REVIEW"),
                    ],
                )
                st.rerun()

        with c2:
            if st.button("Resolve", key="sale_review_resolve", use_container_width=True):
                if not str(admin_note or "").strip():
                    st.error("Admin note is required to resolve.")
                else:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        UPDATE sale_review_requests
                        SET status = 'RESOLVED',
                            admin_note = ?,
                            resolved_by = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (
                            str(admin_note).strip(),
                            st.session_state.get("username", "admin"),
                            int(selected_request_id),
                        ),
                    )
                    cur.execute(
                        """
                        INSERT INTO activity_log
                        (event_type, reference_id, role, username, message)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            "SALE_REVIEW_RESOLVED",
                            int(selected_request_id),
                            "Admin",
                            st.session_state.get("username", "admin"),
                            f"Sale review request {int(selected_request_id)} resolved. {str(admin_note).strip()}",
                        ),
                    )
                    conn.commit()
                    st.session_state["sale_review_admin_selected"] = default_request_label
                    st.session_state["sale_review_admin_note"] = ""
                    show_success_summary(
                        "Request resolved.",
                        [
                            ("Request ID", int(selected_request_id)),
                            ("Status", "RESOLVED"),
                        ],
                    )
                    st.rerun()

        with c3:
            if st.button("Reject", key="sale_review_reject", use_container_width=True):
                if not str(admin_note or "").strip():
                    st.error("Admin note is required to reject.")
                else:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        UPDATE sale_review_requests
                        SET status = 'REJECTED',
                            admin_note = ?,
                            resolved_by = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (
                            str(admin_note).strip(),
                            st.session_state.get("username", "admin"),
                            int(selected_request_id),
                        ),
                    )
                    cur.execute(
                        """
                        INSERT INTO activity_log
                        (event_type, reference_id, role, username, message)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            "SALE_REVIEW_REJECTED",
                            int(selected_request_id),
                            "Admin",
                            st.session_state.get("username", "admin"),
                            f"Sale review request {int(selected_request_id)} rejected. {str(admin_note).strip()}",
                        ),
                    )
                    conn.commit()
                    st.session_state["sale_review_admin_selected"] = default_request_label
                    st.session_state["sale_review_admin_note"] = ""
                    st.warning("Request rejected.")
                    st.rerun()

    st.markdown("### Recent Sale Review Requests")
    if history_df.empty:
        st.info("No sale review history yet.")
    else:
        st.dataframe(history_df, use_container_width=True, hide_index=True)
    conn.close()

# ----------------------------
# MANAGER: REQUEST RETURN (ADMIN APPROVAL)
# ----------------------------
def manager_request_return():
    st.subheader(" Request Return (Admin Approval Required)")

    conn = get_db()
    sales = pd.read_sql(
        """
        SELECT
            s.sale_id,
            s.product_id,
            p.brand,
            p.model,
            p.color,
            s.size,
            s.net_quantity AS quantity,
            s.net_revenue AS revenue
        FROM net_sales s
        JOIN products p ON p.id = s.product_id
        ORDER BY s.sale_id DESC
        """,
        conn
    )

    conn.close()

    if sales.empty:
        st.info("No sales available for return.")
        return

    # ----------------------------
    # Select sale
    # ----------------------------
    sale_placeholder = "Select sale to return"
    sale_ids = sales["sale_id"].tolist()
    sale_option = st.selectbox(
        "Select Sale to Return",
        [sale_placeholder] + sale_ids,
        format_func=lambda x: (
            sale_placeholder if x == sale_placeholder else sales[sales["sale_id"] == x][
                ["brand", "model", "color", "size", "quantity", "revenue"]
            ]
            .iloc[0]
            .to_string()
        )
    )
    if sale_option == sale_placeholder:
        render_theme_notice("Select a sale to continue.")
        return

    sale_row = sales[sales["sale_id"] == sale_option].iloc[0]

    return_size = str(sale_row["size"])
    max_qty = int(
        sale_row["quantity"] - sale_row.get("returned_quantity", 0)
    )
    # ----------------------------
    # Quantity to return
    # ----------------------------
    qty_placeholder = "Select quantity"
    qty_options = [qty_placeholder] + [int(i) for i in range(1, int(max_qty) + 1)]
    qty_selected = st.selectbox(
        "Quantity to return",
        qty_options,
        key="return_qty_select",
    )
    if qty_selected == qty_placeholder:
        render_theme_notice("Select quantity to continue.")
        return
    qty = int(qty_selected)

    st.caption(f"Size: {return_size}")
    st.caption(f"Maximum returnable quantity: {max_qty}")

    notes = st.text_area(
        "Return Reason / Notes",
        placeholder="Reason for return, condition of item, etc."
    )
    refund_amount = st.number_input(
        "Amount Refunded (KES)",
        min_value=0.0,
        step=50.0,
        key="return_refund_amount",
    )
    refund_method = st.selectbox(
        "Refund Method",
        ["Cash", "Mobile Money"],
        key="return_refund_method",
    )

    # ----------------------------
    # Submit request
    # ----------------------------
    if st.button(" Submit Return Request"):
        conn = get_db()
        cur = conn.cursor()

        # Insert return request (SIZE-AWARE)
        cur.execute(
            """
            INSERT INTO returns_exchanges
            (sale_id, type, size, quantity, amount, refund_amount, refund_method, notes, initiated_by, status)
            VALUES (?, 'RETURN', ?, ?, 0, ?, ?, ?, ?, 'PENDING')
            """,
            (
                sale_option,
                return_size,
                qty,
                float(refund_amount),
                str(refund_method),
                notes,
                st.session_state.username
            )
        )

        # Log activity
        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "RETURN_REQUESTED",
                sale_option,
                st.session_state.role,      # Manager
                st.session_state.username,  # Who requested
                f"Size {return_size}, Qty {qty}, Refund KES {float(refund_amount):,.0f} via {refund_method}. {notes}"
            )
        )

        conn.commit()
        conn.close()

        show_success_summary(
            "Return request submitted for admin approval.",
            [
                ("Sale ID", int(sale_option)),
                ("Size", str(return_size)),
                ("Quantity", int(qty)),
                ("Refund (KES)", int(float(refund_amount))),
                ("Refund Method", str(refund_method)),
            ],
        )
        st.session_state["return_refund_amount"] = 0.0
        st.session_state["return_refund_method"] = "Cash"
        st.rerun()

def manager_view_return_status():
    st.subheader(" My Return Requests Status")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT re.id AS request_id,
               re.sale_id,
               re.type,
               re.status,
               COALESCE(re.refund_amount, 0) AS refund_amount,
               COALESCE(re.refund_method, '') AS refund_method,
               re.notes,
               re.created_at
        FROM returns_exchanges re
        WHERE re.initiated_by = ?
          AND re.type = 'RETURN'
        ORDER BY re.created_at DESC
        """,
        conn,
        params=(st.session_state.username,)
    )
    conn.close()

    if df.empty:
        st.info("You have not submitted any return requests yet.")
        return

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df.dropna(subset=["created_at"]).copy()
    if df.empty:
        st.info("You have not submitted any return requests yet.")
        return

    st.markdown("#### Request Period")
    period = st.radio(
        "Select Period",
        ["This Month", "Last Month", "Custom"],
        horizontal=True,
        key="manager_return_status_period",
        label_visibility="collapsed",
    )
    today = datetime.now().date()
    if period == "This Month":
        start_date = today.replace(day=1)
        end_date = today
    elif period == "Last Month":
        first_this = today.replace(day=1)
        end_last = first_this - timedelta(days=1)
        start_date = end_last.replace(day=1)
        end_date = end_last
    else:
        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Start date", value=today.replace(day=1), key="manager_return_status_start")
        with c2:
            end_date = st.date_input("End date", value=today, key="manager_return_status_end")
        if start_date > end_date:
            st.error("Start date cannot be after end date.")
            return

    df = df[(df["created_at"].dt.date >= start_date) & (df["created_at"].dt.date <= end_date)].copy()
    if df.empty:
        render_theme_notice("No return requests in the selected period.")
        return

    # Friendly labels
    df.rename(
        columns={
            "request_id": "Request ID",
            "sale_id": "Sale ID",
            "status": "Status",
            "refund_amount": "Refund Amount (KES)",
            "refund_method": "Refund Method",
            "notes": "Admin / Manager Notes",
            "created_at": "Submitted On"
        },
        inplace=True
    )

    st.dataframe(
        df[
            ["Request ID", "Sale ID", "Status", "Admin / Manager Notes", "Submitted On"]
            if "Refund Amount (KES)" not in df.columns
            else ["Request ID", "Sale ID", "Status", "Refund Amount (KES)", "Refund Method", "Admin / Manager Notes", "Submitted On"]
        ],
        hide_index=True,
        use_container_width=True
    )

#Unified inventory 
def inventory_overview(role):
    st.subheader(" Inventory")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
        p.id AS product_id,
        p.brand,
        p.model,
        p.color,
        p.category,
        p.selling_price,
        p.buying_price,
        p.is_active,
        ps.size,
        ps.quantity
    FROM products p
    LEFT JOIN product_sizes ps ON ps.product_id = p.id
    WHERE NOT (
        LOWER(TRIM(COALESCE(p.category, ''))) = 'external'
        AND LOWER(TRIM(COALESCE(p.brand, ''))) = 'brokered'
        AND LOWER(TRIM(COALESCE(p.model, ''))) = 'brokered sale'
    )
    ORDER BY p.brand, p.model, ps.size
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.info("No products in inventory.")
        return

    def _normalize_group_text(series):
        return (
            series.fillna("")
            .astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

    for col in ["brand", "model", "color", "category"]:
        df[col] = df[col].fillna("").astype(str)
    # Normalize display grouping keys (trim + casefold) so visual duplicates
    # like trailing spaces do not split into separate brand/model/color groups.
    df["brand_clean"] = _normalize_group_text(df["brand"])
    df["model_clean"] = _normalize_group_text(df["model"])
    df["color_clean"] = _normalize_group_text(df["color"])
    df["brand_norm"] = df["brand_clean"].str.casefold()
    df["model_norm"] = df["model_clean"].str.casefold()
    df["color_norm"] = df["color_clean"].str.casefold()

    def _render_color_rows(style_df, color_rows, brand, model, role):
        for _, color_row in color_rows.iterrows():
            pid = int(color_row["product_id"])
            color = str(color_row.get("color_clean", color_row.get("color", "")))
            selling_price = int(color_row["selling_price"] or 0)
            is_active = int(color_row["is_active"] or 0)

            with st.expander(f"Color: {color}", expanded=False):
                status = "Active" if is_active == 1 else "Archived"
                st.caption(f"Status: {status}")

                st.write(f"Selling Price: KES {selling_price}")

                sizes = style_df[style_df["product_id"] == pid].dropna(subset=["size"]).copy()
                if sizes.empty:
                    st.info("No sizes added for this color yet.")
                else:
                    size_view = sizes[["size", "quantity"]].copy()
                    size_view["quantity"] = pd.to_numeric(size_view["quantity"], errors="coerce").fillna(0).astype(int)
                    st.markdown("Size Stock")
                    st.dataframe(size_view, hide_index=True, use_container_width=True)

    brand_norms = sorted(df["brand_norm"].dropna().unique().tolist())

    for brand_norm in brand_norms:
        brand_df = df[df["brand_norm"] == brand_norm].copy()
        brand_label = (
            brand_df["brand_clean"][brand_df["brand_clean"] != ""].mode().iloc[0]
            if not brand_df["brand_clean"][brand_df["brand_clean"] != ""].empty
            else "(Unspecified Brand)"
        )
        brand = brand_label

        with st.expander(brand_label, expanded=False):
            model_norms = sorted(brand_df["model_norm"].dropna().unique().tolist())

            for model_norm in model_norms:
                style_df = brand_df[brand_df["model_norm"] == model_norm].copy()
                model_label = (
                    style_df["model_clean"][style_df["model_clean"] != ""].mode().iloc[0]
                    if not style_df["model_clean"][style_df["model_clean"] != ""].empty
                    else "(Unspecified Model)"
                )
                model = model_label
                color_rows = (
                    style_df[
                        [
                            "product_id",
                            "color",
                            "color_clean",
                            "color_norm",
                            "category",
                            "selling_price",
                            "buying_price",
                            "is_active",
                        ]
                    ]
                    # One UI row per color; prefer active/latest record if duplicates exist.
                    .sort_values(["color_norm", "is_active", "product_id"], ascending=[True, False, False])
                    .drop_duplicates(subset=["color_norm"], keep="first")
                    .reset_index(drop=True)
                )

                with st.expander(f"Model: {model_label}", expanded=False):
                    st.caption(f"Colors available: {len(color_rows)}")

                    _render_color_rows(style_df, color_rows, brand, model, role)

#INVENTORY VALUATION (CLOSING STOCK @ COST)
def inventory_valuation_summary():
    st.subheader(" Inventory Valuation (At Cost)")

    conn = get_db()

    df = pd.read_sql(
        """
        SELECT
            p.id AS product_id,
            p.brand,
            p.model,
            p.color,
            p.buying_price,
            COALESCE(SUM(ps.quantity), 0) AS total_qty
        FROM products p
        LEFT JOIN product_sizes ps ON ps.product_id = p.id
        WHERE p.is_active = 1
        GROUP BY p.id
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.info("No inventory data available.")
        return

    df["buying_price"] = pd.to_numeric(df["buying_price"], errors="coerce")
    df["stock_value"] = df["buying_price"] * df["total_qty"]

    missing_cost = df[df["buying_price"].isna()]
    valid = df.dropna(subset=["buying_price"])

    total_value = int(valid["stock_value"].sum())
        # ----------------------------
    # STOCK IN TRANSIT VALUE
    # ----------------------------
    conn = get_db()
    transit = pd.read_sql(
        """
        SELECT SUM(quantity * unit_cost) AS transit_value
        FROM stock_in_transit
        """,
        conn
    )
    conn.close()

    transit_value = int(transit["transit_value"].iloc[0] or 0)

    st.divider()

    c3, c4 = st.columns(2)
    c3.metric("On-Hand Stock Value (KES)", total_value)
    c4.metric("Stock In Transit Value (KES)", transit_value)

    st.metric(
        " Total Inventory Value (On-Hand + Transit)",
        total_value + transit_value
    )

    # ---- KPIs ----
    c1, c2 = st.columns(2)
    c1.metric("Total Units in Stock", int(valid["total_qty"].sum()))
    c2.metric("Total Stock Value (KES)", total_value)

    st.divider()

    # ---- Warnings ----
    if not missing_cost.empty:
        st.warning(" Some products have NO buying price  valuation incomplete")
    st.dataframe(
            missing_cost[["brand", "model", "color", "total_qty"]],
            hide_index=True,
            use_container_width=True
        )

    # ---- Detailed table ----
    st.markdown("###  Inventory Value Breakdown")

    view = valid.copy()
    view["stock_value"] = view["stock_value"].astype(int)

    st.dataframe(
        view.rename(columns={
            "brand": "Brand",
            "model": "Model",
            "color": "Color",
            "buying_price": "Unit Cost",
            "total_qty": "Quantity",
            "stock_value": "Stock Value (KES)"
        })[
            ["Brand", "Model", "Color", "Quantity", "Unit Cost", "Stock Value (KES)"]
        ],
        hide_index=True,
        use_container_width=True
    )

#Add stock in transit
def add_stock_in_transit(role):
    st.subheader(" Add Stock In Transit (Paid, Not Yet Received)")

    conn = get_db()
    products = pd.read_sql(
        "SELECT id, brand, model, color, category, buying_price FROM products WHERE is_active = 1",
        conn
    )
    conn.close()

    if products.empty:
        st.info("No active products available.")
        return

    product_id = st.selectbox( 
        "Select Product",
        products["id"],
        format_func=lambda x: (
            products[products["id"] == x][["brand", "model", "color"]]
            .iloc[0]
            .to_string()
        ),
        key=f"select_product_stock_transit_{role}"
    )

    product = products[products["id"] == product_id].iloc[0]

    # Size logic: full category range + existing/custom product sizes.
    conn_sizes = get_db()
    existing_sizes_df = pd.read_sql(
        "SELECT size FROM product_sizes WHERE product_id = ? ORDER BY size",
        conn_sizes,
        params=(int(product_id),),
    )
    conn_sizes.close()
    existing_sizes = set(existing_sizes_df["size"].dropna().astype(str).tolist()) if not existing_sizes_df.empty else set()
    if str(product["category"]).strip().lower() == "women":
        category_sizes = {str(s) for s in range(35, 42)}
    else:
        category_sizes = {str(s) for s in range(40, 46)}
    allowed_sizes = sorted(existing_sizes.union(category_sizes), key=lambda x: (len(str(x)), str(x)))

    size = st.selectbox(
        "Size",
        allowed_sizes,
        key=f"stock_transit_size_{role}"
    )


    quantity = st.number_input(
        "Quantity",
        min_value=1,
        step=1,
        key=f"stock_transit_qty_{role}"
    )

    default_cost = product["buying_price"] or 0

    unit_cost = st.number_input(
        "Unit Cost (KES)",
        min_value=0,
        value=int(default_cost),
        key=f"stock_transit_unit_cost_{role}"

    )

    total_cost = quantity * unit_cost
    st.caption(f" Total Value: KES {total_cost}")

    if st.button(
        " Record Stock In Transit",
        key=f"stock_transit_submit_{role}"
    ):
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO stock_in_transit
            (product_id, size, quantity, unit_cost, total_cost, entered_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                size,
                quantity,
                unit_cost,
                total_cost,
                st.session_state.username
            )
        )

        # Audit trail
        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, role, username, message)
            VALUES (?, ?, ?, ?)
            """,
            (
                "STOCK_IN_TRANSIT_ADDED",
                role,
                st.session_state.username,
                f"Product ID {product_id}, Size {size}, Qty {quantity}, Value KES {total_cost}"
            )
        )

        conn.commit()
        conn.close()

        show_success_summary(
            "Stock in transit recorded successfully.",
            [
                ("Product ID", int(product_id)),
                ("Size", str(size)),
                ("Quantity", int(quantity)),
                ("Unit Cost (KES)", int(unit_cost)),
                ("Total Value (KES)", int(total_cost)),
            ],
        )

#View Stock In transit
def view_stock_in_transit():
    st.subheader(" Stock In Transit (Paid, Not Yet Received)")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            p.brand,
            p.model,
            p.color,
            st.size,
            st.quantity,
            st.unit_cost,
            st.total_cost,
            st.entered_by,
            st.created_at
        FROM stock_in_transit st
        JOIN products p ON p.id = st.product_id
        ORDER BY st.created_at DESC
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.info("No stock currently in transit.")
        return

    df["created_at"] = pd.to_datetime(df["created_at"])

    st.dataframe(
        df.rename(columns={
            "brand": "Brand",
            "model": "Model",
            "color": "Color",
            "size": "Size",
            "quantity": "Qty",
            "unit_cost": "Unit Cost",
            "total_cost": "Total Value",
            "entered_by": "Entered By",
            "created_at": "Recorded At"
        }),
        hide_index=True,
        use_container_width=True
    ) #--------

#record opening inventory 
def record_opening_inventory():
    st.subheader(" Record Opening Inventory (For COGS)")

    snapshot_date = st.date_input("Opening Inventory Date")
    total_value = st.number_input(
        "Opening Inventory Value (KES)",
        min_value=0.0,
        step=1.0
    )

    if st.button(" Save Opening Inventory"):
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO opening_inventory
            (snapshot_date, total_value, created_by)
            VALUES (?, ?, ?)
            """,
            (snapshot_date, total_value, st.session_state.username)
        )

        conn.commit()
        conn.close()

        show_success_summary(
            "Opening inventory recorded.",
            [
                ("Snapshot Date", snapshot_date.strftime("%Y-%m-%d")),
                ("Total Value (KES)", int(total_value)),
            ],
        )
#COGS Summary
def cogs_summary():
    st.subheader(" Cost of Goods Sold (COGS)")

    # ----------------------------
    # Period selector
    # ----------------------------
    period = st.radio(
        "Select Period",
        ["Today", "This Month", "Custom"],
        horizontal=True
    )

    today = pd.Timestamp.today().normalize()

    if period == "Today":
        start_date = end_date = today

    elif period == "This Month":
        start_date = today.replace(day=1)
        end_date = today

    else:
        col1, col2 = st.columns(2)
        with col1:
            start_date = pd.to_datetime(st.date_input("Start date", today))
        with col2:
            end_date = pd.to_datetime(st.date_input("End date", today))

    # ----------------------------
    # Load sales cost data
    # ----------------------------
    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            s.sale_date,
            s.net_cost AS cost,
            s.net_quantity AS quantity,
            p.brand,
            p.model,
            p.color
        FROM net_sales s
        JOIN products p ON p.id = s.product_id
        WHERE s.sale_date BETWEEN ? AND ?
        """,
        conn,
        params=(
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        )
    )

    conn.close()

    if df.empty:
        st.info("No sales recorded for selected period.")
        return

    df["cost"] = pd.to_numeric(df["cost"], errors="coerce").fillna(0)

    total_cogs = int(df["cost"].sum())
    total_units = int(df["quantity"].sum())

    # ----------------------------
    # KPIs
    # ----------------------------
    c1, c2 = st.columns(2)
    c1.metric("Total Units Sold", total_units)
    c2.metric("Total COGS (KES)", total_cogs)

    st.divider()

    # ----------------------------
    # Breakdown by product
    # ----------------------------
    breakdown = (
        df.groupby(["brand", "model", "color"])
        .agg(
            units_sold=("quantity", "sum"),
            cogs=("cost", "sum")
        )
        .reset_index()
    )

    breakdown["cogs"] = breakdown["cogs"].astype(int)

    st.markdown("###  COGS Breakdown by Product")

    st.dataframe(
        breakdown.rename(columns={
            "brand": "Brand",
            "model": "Model",
            "color": "Color",
            "units_sold": "Units Sold",
            "cogs": "COGS (KES)"
        }),
        hide_index=True,
        use_container_width=True
    )

#Admin record Operating Expenses
def record_operating_expense():
    st.subheader("Record Operating Expense")

    if st.session_state.get("op_expense_reset_form"):
        st.session_state["op_record_expense_date"] = datetime.now().date()
        st.session_state["op_record_expense_category"] = OPERATING_EXPENSE_VOTEHEADS[0]
        st.session_state["op_record_expense_description"] = ""
        st.session_state["op_record_expense_amount"] = 0.0
        st.session_state["op_expense_reset_form"] = False

    if st.session_state.get("op_expense_flash"):
        saved = st.session_state.get("op_expense_last_saved", {})
        show_success_summary(
            "Operating expense saved.",
            [
                ("Date", saved.get("expense_date", "")),
                ("Category", saved.get("category", "")),
                ("Description", saved.get("description", "")),
                ("Amount (KES)", f"{int(saved.get('amount', 0)):,}"),
                ("Expense ID", f"#{saved.get('expense_id', '')}"),
            ],
        )
        st.session_state.op_expense_flash = False

    expense_date = st.date_input("Expense Date", key="op_record_expense_date")
    category = st.selectbox(
        "Expense Category",
        OPERATING_EXPENSE_VOTEHEADS,
        key="op_record_expense_category",
    )

    description = st.text_input("Description (optional)", key="op_record_expense_description")
    amount = st.number_input("Amount (KES)", min_value=0.0, step=1.0, key="op_record_expense_amount")

    if st.button("Review Expense", key="op_record_review_expense"):
        if float(amount) <= 0:
            st.error(" Expense amount must be greater than 0.")
        else:
            st.session_state.op_expense_pending = {
                "expense_date": expense_date.strftime("%Y-%m-%d"),
                "category": str(category),
                "description": str(description or "").strip(),
                "amount": int(amount),
            }

    pending = st.session_state.get("op_expense_pending")
    if pending:
        st.markdown("### Expense Summary (Confirm Before Save)")
        st.write(f"Date: {pending['expense_date']}")
        st.write(f"Category: {pending['category']}")
        st.write(f"Description: {pending['description'] or '-'}")
        st.write(f"Amount: KES {int(pending['amount']):,}")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Edit Entry", key="op_record_edit_pending"):
                st.session_state.pop("op_expense_pending", None)
                st.rerun()
        with c2:
            if st.button("Confirm & Save Operating Expense", key="op_record_confirm_save"):
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO operating_expenses
                    (expense_date, category, description, amount, created_by)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        pending["expense_date"],
                        pending["category"],
                        pending["description"],
                        int(pending["amount"]),
                        st.session_state.username,
                    )
                )
                expense_id = int(cur.lastrowid)
                cur.execute(
                    """
                    INSERT INTO activity_log
                    (event_type, reference_id, role, username, message)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "OPERATING_EXPENSE",
                        expense_id,
                        st.session_state.get("role", "Admin"),
                        st.session_state.get("username", "admin"),
                        f"Operating expense: {pending['category']} - KES {int(pending['amount'])}",
                    )
                )
                conn.commit()
                conn.close()

                st.session_state.op_expense_last_saved = {
                    "expense_id": expense_id,
                    **pending,
                }
                st.session_state.op_expense_flash = True
                st.session_state.pop("op_expense_pending", None)
                st.session_state["op_expense_reset_form"] = True
                st.rerun()


#Operating Expenses Entry
def operating_expenses_entry():
    st.subheader("Record Operating Expense")

    expense_date = st.date_input(
        "Expense Date",
        pd.Timestamp.today(),
        key="op_new_date",
    )

    category = st.selectbox(
        "Expense Category",
        OPERATING_EXPENSE_VOTEHEADS,
        key="op_new_category",
    )

    description = st.text_input(
        "Description (optional)",
        placeholder="e.g. January shop rent, fuel for deliveries",
        key="op_new_description",
    )

    amount = st.number_input(
        "Amount (KES)",
        min_value=0,
        step=100,
        key="op_new_amount",
    )

    if st.button("Save Expense"):
        if amount <= 0:
            st.error("Expense amount must be greater than 0.")
            return

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO operating_expenses
            (expense_date, category, description, amount)
            VALUES (?, ?, ?, ?)
            """,
            (
                expense_date.strftime("%Y-%m-%d"),
                category,
                description,
                int(amount)
            )
        )

        # Log activity
        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "OPERATING_EXPENSE",
                cur.lastrowid,
                st.session_state.role,
                st.session_state.username,
                f"Operating expense: {category} - KES {int(amount)}"
            )
        )

        conn.commit()
        conn.close()

        show_success_summary(
            "Operating expense saved.",
            [
                ("Date", expense_date.strftime("%Y-%m-%d")),
                ("Category", category),
                ("Description", description or "-"),
                ("Amount (KES)", f"{int(amount):,}"),
            ],
        )
        st.session_state["op_new_date"] = pd.Timestamp.today()
        st.session_state["op_new_category"] = OPERATING_EXPENSE_VOTEHEADS[0]
        st.session_state["op_new_description"] = ""
        st.session_state["op_new_amount"] = 0
        st.rerun()

    st.divider()
    st.subheader("Edit Operating Expense")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, expense_date, category, description, amount
        FROM operating_expenses
        ORDER BY expense_date DESC, id DESC
        LIMIT 50
    """)
    rows = cur.fetchall()
    conn.close()
    if not rows:
        st.info("No operating expenses to edit yet.")
    else:
        options = {f"#{r[0]} | {r[1]} | {r[2]} | KES {int(r[4])}": r for r in rows}
        selected_label = st.selectbox("Select expense to edit", list(options.keys()))
        selected = options[selected_label]
        selected_id = int(selected[0])
        selected_date = str(selected[1])
        selected_category = str(selected[2] or "")
        selected_description = str(selected[3] or "")
        selected_amount = int(selected[4] or 0)

        # Keep edit constrained to known voteheads but still support legacy categories.
        category_options = list(OPERATING_EXPENSE_VOTEHEADS)
        if selected_category and selected_category not in category_options:
            category_options = [selected_category] + category_options
        category_index = category_options.index(selected_category) if selected_category in category_options else 0

        with st.form("op_edit_form"):
            edit_date = st.date_input(
                "Expense Date (edit)",
                pd.to_datetime(selected_date),
                key="op_edit_date",
            )
            edit_category = st.selectbox(
                "Category (edit)",
                category_options,
                index=category_index,
                key="op_edit_category",
            )
            edit_description = st.text_input(
                "Description (edit)",
                selected_description,
                key="op_edit_description",
            )
            edit_amount = st.number_input(
                "Amount (KES) (edit)",
                min_value=0,
                step=100,
                value=selected_amount,
                key="op_edit_amount",
            )
            update_clicked = st.form_submit_button(" Update Expense")

        if update_clicked:
            if edit_amount <= 0:
                st.error(" Expense amount must be greater than 0.")
            else:
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE operating_expenses
                    SET expense_date = ?, category = ?, description = ?, amount = ?
                    WHERE id = ?
                    """,
                    (
                        edit_date.strftime("%Y-%m-%d"),
                        str(edit_category),
                        str(edit_description),
                        int(edit_amount),
                        selected_id,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO activity_log
                    (event_type, reference_id, role, username, message)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "OPERATING_EXPENSE_EDITED",
                        selected_id,
                        st.session_state.get("role", "Admin"),
                        st.session_state.get("username", "admin"),
                        (
                            f"Updated operating expense #{selected_id}: "
                            f"{selected_date} | {selected_category} | {selected_description} | KES {selected_amount:,} "
                            f"-> {edit_date.strftime('%Y-%m-%d')} | {edit_category} | {edit_description} | KES {int(edit_amount):,}"
                        ),
                    ),
                )
                conn.commit()
                conn.close()
                show_success_summary(
                    "Expense updated.",
                    [
                        ("Expense ID", int(selected_id)),
                        ("Date", edit_date.strftime("%Y-%m-%d")),
                        ("Category", str(edit_category)),
                        ("Amount (KES)", f"{int(edit_amount):,}"),
                    ],
                )

        st.markdown("###  Delete Expense")
        with st.form("op_delete_form"):
            st.warning("This will permanently remove the selected operating expense.")
            delete_confirm = st.text_input(
                "Type DELETE EXPENSE to confirm",
                key="op_delete_confirm",
            )
            delete_clicked = st.form_submit_button(" Delete Expense")

        if delete_clicked:
            if delete_confirm.strip().upper() != "DELETE EXPENSE":
                st.error(" Confirmation text mismatch. Expense not deleted.")
            else:
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    """
                    DELETE FROM operating_expenses
                    WHERE id = ?
                    """,
                    (selected_id,),
                )
                cur.execute(
                    """
                    INSERT INTO activity_log
                    (event_type, reference_id, role, username, message)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "OPERATING_EXPENSE_DELETED",
                        selected_id,
                        st.session_state.get("role", "Admin"),
                        st.session_state.get("username", "admin"),
                        f"Deleted operating expense #{selected_id}: {selected_date} | {selected_category} | {selected_description} | KES {selected_amount:,}",
                    ),
                )
                conn.commit()
                conn.close()
                show_success_summary(
                    "Expense deleted.",
                    [
                        ("Expense ID", int(selected_id)),
                        ("Category", str(selected_category)),
                        ("Amount (KES)", f"{int(selected_amount):,}"),
                    ],
                )
                st.rerun()

# Home Expenses (Manager/Admin)
def home_expenses_entry():
    st.subheader(" Home Expenses")
    if st.session_state.get("home_expense_flash"):
        payload = st.session_state.get("home_expense_last_payload", {})
        show_success_summary(
            "Home expense recorded successfully.",
            [
                ("Date", payload.get("date", "")),
                ("Category", payload.get("category", "")),
                ("Amount (KES)", f"{int(payload.get('amount', 0)):,}"),
                ("Description", payload.get("description", "")),
            ],
        )
        st.session_state.home_expense_flash = False

    st.markdown("### Step 1: Select Expense Date")
    expense_date = st.date_input("Expense Date", pd.Timestamp.today())
    st.caption(f" Selected date: {expense_date.strftime('%Y-%m-%d')}")

    st.markdown("### Step 2: Expense Details")
    category = st.selectbox(
        "Expense Category",
        [
            "Rent",
            "Electricity (Power)",
            "Water",
            "Internet",
            "Garbage Collection",
            "Food & Groceries",
            "Transport / Fuel",
            "School Fees",
            "Medical / Health",
            "Household Supplies",
            "Clothing",
            "Personal Care",
            "Entertainment",
            "Insurance",
            "Loan Repayment",
            "Savings / Investments",
            "Repairs & Maintenance",
            "Gifts / Donations",
            "Childcare",
            "Mobile Airtime",
            "Other"
        ]
    )
    description = st.text_area(
        "Additional Notes (optional)",
        placeholder="Add more details if needed..."
    )
    amount = st.number_input("Amount (KES)", min_value=0, step=100)

    st.markdown("### Step 3: Review & Submit")
    st.markdown("**Expense Summary:**")
    st.write(f"Date: {expense_date.strftime('%Y-%m-%d')}")
    st.write(f"Category: {category}")
    st.write(f"Description: {description or category}")
    st.write(f"Amount: KES {int(amount)}")

    if st.button(" Submit Home Expense"):
        if amount <= 0:
            st.error(" Amount must be greater than 0.")
            return
        clean_description = (description or category).strip()
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO home_expenses
            (expense_date, category, description, amount, created_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                expense_date.strftime("%Y-%m-%d"),
                category,
                clean_description,
                int(amount),
                st.session_state.username
            )
        )
        # Log activity
        cur.execute(
            """
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "HOME_EXPENSE",
                cur.lastrowid,
                st.session_state.role,
                st.session_state.username,
                f"Home expense: {category} - KES {int(amount)}"
            )
        )

        conn.commit()
        conn.close()
        st.session_state.home_expense_last_payload = {
            "date": expense_date.strftime("%Y-%m-%d"),
            "category": category,
            "description": clean_description,
            "amount": int(amount),
        }
        st.session_state.home_expense_flash = True
        st.rerun()

    st.divider()
    st.subheader(" Edit Home Expense")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, expense_date, category, description, amount
        FROM home_expenses
        ORDER BY expense_date DESC, id DESC
        LIMIT 50
    """)
    rows = cur.fetchall()
    conn.close()
    if not rows:
        st.info("No home expenses to edit yet.")
    else:
        options = {f"#{r[0]}  {r[1]}  {r[2]}  KES {int(r[4])}": r for r in rows}
        selected_label = st.selectbox("Select home expense to edit", list(options.keys()))
        selected = options[selected_label]
        edit_date = st.date_input("Home Expense Date (edit)", pd.to_datetime(selected[1]), key="home_edit_date")
        edit_category = st.text_input("Category (edit)", selected[2] or "", key="home_edit_category")
        edit_description = st.text_input("Description (edit)", selected[3] or "", key="home_edit_description")
        edit_amount = st.number_input("Amount (KES) (edit)", min_value=0, step=100, value=int(selected[4]), key="home_edit_amount")
        if st.button(" Update Home Expense"):
            if edit_amount <= 0:
                st.error(" Amount must be greater than 0.")
            else:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE home_expenses
                    SET expense_date = ?, category = ?, description = ?, amount = ?
                    WHERE id = ?
                """, (edit_date.strftime("%Y-%m-%d"), edit_category, edit_description, int(edit_amount), int(selected[0])))
                conn.commit()
                conn.close()
                show_success_summary(
                    "Home expense updated.",
                    [
                        ("Expense ID", int(selected[0])),
                        ("Date", edit_date.strftime("%Y-%m-%d")),
                        ("Category", str(edit_category)),
                        ("Amount (KES)", f"{int(edit_amount):,}"),
                    ],
                )

def home_expenses_summary(start_date=None, end_date=None):
    st.subheader(" Home Expenses Summary")
    conn = get_db()
    cur = conn.cursor()
    if not start_date or not end_date:
        end_date = pd.Timestamp.today()
        start_date = end_date - pd.Timedelta(days=30)
    cur.execute("""
        SELECT expense_date, category, description, amount
        FROM home_expenses
        WHERE expense_date BETWEEN ? AND ?
        ORDER BY expense_date DESC
    """, (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))
    rows = cur.fetchall()
    if not rows:
        st.info("No home expenses recorded yet.")
        conn.close()
        return
    df = pd.DataFrame(rows, columns=["expense_date", "category", "description", "amount"])
    total = int(df["amount"].sum())
    st.metric("Total Home Expenses (KES)", total)
    st.dataframe(df, hide_index=True, use_container_width=True)
    breakdown = (
        df.groupby("category")["amount"]
        .sum()
        .reset_index()
        .sort_values(by="amount", ascending=False)
    )
    st.markdown("###  Home Expenses by Category")
    st.dataframe(
        breakdown.rename(columns={"category": "Category", "amount": "Amount (KES)"}),
        hide_index=True,
        use_container_width=True
    )
    conn.close()

def home_expenses_monthly_report():
    st.subheader(" Home Expenses Monthly Report")
    conn = get_db()
    cur = conn.cursor()
    month = st.date_input("Select Month", pd.Timestamp.today(), key="home_expenses_month")
    month_str = month.strftime("%Y-%m")
    cur.execute("""
        SELECT SUM(amount)
        FROM home_expenses
        WHERE strftime('%Y-%m', expense_date) = ?
    """, (month_str,))
    total = cur.fetchone()[0] or 0
    st.metric("Total Home Expenses (KES)", int(total))
    cur.execute("""
        SELECT expense_date, category, description, amount
        FROM home_expenses
        WHERE strftime('%Y-%m', expense_date) = ?
        ORDER BY expense_date DESC
    """, (month_str,))
    rows = cur.fetchall()
    if rows:
        df = pd.DataFrame(rows, columns=["expense_date", "category", "description", "amount"])
        st.dataframe(df, hide_index=True, use_container_width=True)
        breakdown = (
            df.groupby("category")["amount"]
            .sum()
            .reset_index()
            .sort_values(by="amount", ascending=False)
        )
        st.markdown("###  Home Expenses by Category (Monthly)")
        st.dataframe(
            breakdown.rename(columns={"category": "Category", "amount": "Amount (KES)"}),
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No home expenses recorded for this month.")
    conn.close()

#Operating expenses summary totals and breakdown
def operating_expenses_summary(start_date=None, end_date=None):
    st.subheader("Operating Expenses Summary")

    conn = get_db()
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    today = pd.Timestamp.today()
    years_df = pd.read_sql(
        "SELECT DISTINCT strftime('%Y', expense_date) AS y FROM operating_expenses WHERE expense_date IS NOT NULL ORDER BY y",
        conn,
    )
    years = []
    for y in years_df.get("y", []):
        try:
            years.append(int(y))
        except Exception:
            pass
    if not years:
        years = [int(today.year)]
    if int(today.year) not in years:
        years.append(int(today.year))
    years = sorted(set(years))

    def month_bounds(year_value, month_value):
        start = pd.Timestamp(year=int(year_value), month=int(month_value), day=1)
        end = start + pd.offsets.MonthEnd(1)
        return start, end

    def load_expenses_for_period(start_ts, end_ts):
        return pd.read_sql(
            """
            SELECT expense_date, category, description, amount
            FROM operating_expenses
            WHERE expense_date BETWEEN ? AND ?
            ORDER BY expense_date DESC
            """,
            conn,
            params=(start_ts.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d")),
        )

    def normalize_expenses_df(df_in):
        if df_in.empty:
            return df_in
        df_out = df_in.copy()
        df_out["amount"] = pd.to_numeric(df_out["amount"], errors="coerce").fillna(0)
        df_out["expense_date"] = pd.to_datetime(df_out["expense_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        df_out["description"] = df_out["description"].fillna("").astype(str)
        return df_out

    mode = "Single Month"
    if start_date and end_date:
        df = load_expenses_for_period(pd.to_datetime(start_date), pd.to_datetime(end_date))
        st.caption(f"Showing operating expenses from {start_date} to {end_date}")
    else:
        mode = st.radio(
            "View Mode",
            ["Single Month", "Month Range", "Compare Months"],
            horizontal=True,
            key="operating_expenses_view_mode",
        )

        if mode == "Single Month":
            c_month, c_year = st.columns(2)
            with c_month:
                selected_month_name = st.selectbox(
                    "Month",
                    month_names,
                    index=int(today.month) - 1,
                    key="operating_expenses_summary_month_name",
                )
            with c_year:
                selected_year = st.selectbox(
                    "Year",
                    years,
                    index=years.index(int(today.year)),
                    key="operating_expenses_summary_year",
                )
            selected_month_num = month_names.index(selected_month_name) + 1
            month_start, month_end = month_bounds(selected_year, selected_month_num)
            st.caption(f"Showing operating expenses for {month_start.strftime('%B %Y')}")
            df = load_expenses_for_period(month_start, month_end)

        elif mode == "Month Range":
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                start_month_name = st.selectbox(
                    "Start Month",
                    month_names,
                    index=int(today.month) - 1,
                    key="operating_expenses_range_start_month",
                )
            with c2:
                start_year = st.selectbox(
                    "Start Year",
                    years,
                    index=years.index(int(today.year)),
                    key="operating_expenses_range_start_year",
                )
            with c3:
                end_month_name = st.selectbox(
                    "End Month",
                    month_names,
                    index=int(today.month) - 1,
                    key="operating_expenses_range_end_month",
                )
            with c4:
                end_year = st.selectbox(
                    "End Year",
                    years,
                    index=years.index(int(today.year)),
                    key="operating_expenses_range_end_year",
                )

            range_start, _ = month_bounds(start_year, month_names.index(start_month_name) + 1)
            _, range_end = month_bounds(end_year, month_names.index(end_month_name) + 1)
            if range_start > range_end:
                st.error("Start month must be before or equal to end month.")
                conn.close()
                return
            st.caption(
                f"Showing operating expenses from {range_start.strftime('%B %Y')} "
                f"to {range_end.strftime('%B %Y')}"
            )
            df = load_expenses_for_period(range_start, range_end)

        else:
            ca1, ca2, cb1, cb2 = st.columns(4)
            with ca1:
                month_a_name = st.selectbox(
                    "Month A",
                    month_names,
                    index=max(int(today.month) - 2, 0),
                    key="operating_expenses_cmp_a_month",
                )
            with ca2:
                year_a = st.selectbox(
                    "Year A",
                    years,
                    index=years.index(int(today.year)),
                    key="operating_expenses_cmp_a_year",
                )
            with cb1:
                month_b_name = st.selectbox(
                    "Month B",
                    month_names,
                    index=int(today.month) - 1,
                    key="operating_expenses_cmp_b_month",
                )
            with cb2:
                year_b = st.selectbox(
                    "Year B",
                    years,
                    index=years.index(int(today.year)),
                    key="operating_expenses_cmp_b_year",
                )

            a_start, a_end = month_bounds(year_a, month_names.index(month_a_name) + 1)
            b_start, b_end = month_bounds(year_b, month_names.index(month_b_name) + 1)
            df_a = normalize_expenses_df(load_expenses_for_period(a_start, a_end))
            df_b = normalize_expenses_df(load_expenses_for_period(b_start, b_end))
            conn.close()

            total_a = int(df_a["amount"].sum()) if not df_a.empty else 0
            total_b = int(df_b["amount"].sum()) if not df_b.empty else 0
            delta = total_b - total_a
            delta_pct = 0.0 if total_a == 0 else (delta / total_a) * 100.0

            label_a = a_start.strftime("%b %Y")
            label_b = b_start.strftime("%b %Y")
            k1, k2, k3 = st.columns(3)
            k1.metric(f"{label_a} Total (KES)", total_a)
            k2.metric(f"{label_b} Total (KES)", total_b)
            k3.metric("Delta (KES)", delta, f"{delta_pct:.1f}%")

            by_a = (
                df_a.groupby("category")["amount"].sum().reset_index().rename(columns={"amount": label_a})
                if not df_a.empty
                else pd.DataFrame(columns=["category", label_a])
            )
            by_b = (
                df_b.groupby("category")["amount"].sum().reset_index().rename(columns={"amount": label_b})
                if not df_b.empty
                else pd.DataFrame(columns=["category", label_b])
            )
            comparison = by_a.merge(by_b, on="category", how="outer").fillna(0)
            if comparison.empty:
                st.info("No operating expenses recorded in both selected months.")
                return

            comparison["Delta (KES)"] = comparison[label_b] - comparison[label_a]
            comparison = comparison.sort_values(by="Delta (KES)", key=lambda s: s.abs(), ascending=False)

            st.markdown("###  Category Comparison")
            st.dataframe(
                comparison.rename(columns={"category": "Category"}),
                hide_index=True,
                use_container_width=True,
            )
            st.bar_chart(comparison.set_index("category")[[label_a, label_b]])

            st.markdown("###  Category Details")
            for _, row in comparison.iterrows():
                category = str(row["category"])
                with st.expander(
                    f"{category}  {label_a}: KES {int(row[label_a]):,} | {label_b}: KES {int(row[label_b]):,}",
                    expanded=False,
                ):
                    left, right = st.columns(2)
                    with left:
                        st.caption(label_a)
                        a_rows = df_a[df_a["category"] == category].copy()
                        if a_rows.empty:
                            st.info("No entries.")
                        else:
                            a_rows["amount"] = a_rows["amount"].astype(int)
                            st.dataframe(
                                a_rows.rename(
                                    columns={
                                        "expense_date": "Date",
                                        "description": "Description",
                                        "amount": "Amount (KES)",
                                    }
                                )[["Date", "Description", "Amount (KES)"]],
                                hide_index=True,
                                use_container_width=True,
                            )
                    with right:
                        st.caption(label_b)
                        b_rows = df_b[df_b["category"] == category].copy()
                        if b_rows.empty:
                            st.info("No entries.")
                        else:
                            b_rows["amount"] = b_rows["amount"].astype(int)
                            st.dataframe(
                                b_rows.rename(
                                    columns={
                                        "expense_date": "Date",
                                        "description": "Description",
                                        "amount": "Amount (KES)",
                                    }
                                )[["Date", "Description", "Amount (KES)"]],
                                hide_index=True,
                                use_container_width=True,
                            )
            return

    conn.close()
    df = normalize_expenses_df(df)

    if df.empty:
        st.info("No operating expenses recorded yet.")
        return

    total_expenses = int(df["amount"].sum())
    st.metric("Total Operating Expenses (KES)", total_expenses)

    st.divider()

    by_category = (
        df.groupby("category")["amount"]
        .sum()
        .reset_index()
        .sort_values(by="amount", ascending=False)
    )

    st.markdown("###  Expenses by Category")
    st.dataframe(
        by_category.rename(columns={
            "category": "Category",
            "amount": "Amount (KES)"
        }),
        hide_index=True,
        use_container_width=True
    )
    st.bar_chart(by_category.set_index("category")["amount"])

    st.markdown("###  Category Details")
    st.caption("Open any category to view the exact dates, descriptions, and amounts as originally recorded.")
    for _, row in by_category.iterrows():
        category = str(row["category"])
        cat_total = int(row["amount"])
        with st.expander(f"{category}  KES {cat_total:,}", expanded=False):
            cat_df = df[df["category"] == category].copy()
            cat_df["amount"] = cat_df["amount"].astype(int)
            st.dataframe(
                cat_df.rename(
                    columns={
                        "expense_date": "Date",
                        "description": "Description",
                        "amount": "Amount (KES)",
                    }
                )[["Date", "Description", "Amount (KES)"]],
                hide_index=True,
                use_container_width=True,
            )
#Detailed operating expenses view - for audit
def operating_expenses_detailed():
    st.subheader("Operating Expenses - Detailed View")

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT
            expense_date,
            category,
            description,
            amount,
            created_at
        FROM operating_expenses
        ORDER BY expense_date DESC
        """,
        conn
    )
    conn.close()

    if df.empty:
        st.info("No operating expenses available.")
        return

    df["amount"] = df["amount"].astype(int)

    st.dataframe(
        df.rename(columns={
            "expense_date": "Date",
            "category": "Category",
            "description": "Description",
            "amount": "Amount (KES)",
            "created_at": "Recorded At"
        }),
        hide_index=True,
        use_container_width=True
    )
#P&L Summary
def profit_and_loss_statement():
    st.subheader("Profit and Loss Statement")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("P&L Start Date", key="pl_start")
    with col2:
        end_date = st.date_input("P&L End Date", key="pl_end")

    conn = get_db()

    # ----------------------------
    # REVENUE (NET OF RETURNS)
    # ----------------------------
    revenue = pd.read_sql(
        """
        SELECT SUM(net_revenue) AS total
        FROM net_sales
        WHERE sale_date BETWEEN ? AND ?
        """,
        conn,
        params=(start_date, end_date)
    )["total"].iloc[0] or 0

    # ----------------------------
    # COGS (TRANSACTIONAL  NET OF RETURNS)
    # ----------------------------
    cogs = pd.read_sql(
        """
        SELECT SUM(net_cost) AS total
        FROM net_sales
        WHERE sale_date BETWEEN ? AND ?
        """,
        conn,
        params=(start_date, end_date)
    )["total"].iloc[0] or 0

    # ----------------------------
    # OPERATING EXPENSES
    # ----------------------------
    expenses = pd.read_sql(
        """
        SELECT SUM(amount) AS total
        FROM operating_expenses
        WHERE expense_date BETWEEN ? AND ?
        """,
        conn,
        params=(start_date, end_date)
    )["total"].iloc[0] or 0

    conn.close()

    gross_profit = revenue - cogs
    net_profit = gross_profit - expenses

    # ---------------- DISPLAY ----------------
    st.markdown("### Profit and Loss Summary")

    c1, c2, c3 = st.columns(3)
    c1.metric("Revenue (KES)", int(revenue))
    c2.metric("COGS (KES)", int(cogs))
    c3.metric("Gross Profit (KES)", int(gross_profit))

    st.divider()

    c4, c5 = st.columns(2)
    c4.metric("Operating Expenses (KES)", int(expenses))
    c5.metric("Net Profit (KES)", int(net_profit))


#Balance Sheet
def balance_sheet():
    st.subheader("Balance Sheet")

    as_of = st.date_input(
        "As at Date",
        pd.Timestamp.today(),
        key="bs_date"
    )

    date_str = as_of.strftime("%Y-%m-%d")

    conn = get_db()

    # ----------------------------
    # ASSETS
    # ----------------------------

    # 1 Inventory on hand (at cost)
    inventory = pd.read_sql(
        """
        SELECT SUM(ps.quantity * p.buying_price) AS total
        FROM products p
        JOIN product_sizes ps ON ps.product_id = p.id
        WHERE p.is_active = 1
        """,
        conn
    )
    inventory_value = int(inventory.iloc[0]["total"] or 0)

    # 2 Stock in transit (already paid)
    transit = pd.read_sql(
        """
        SELECT SUM(total_cost) AS total
        FROM stock_in_transit
        WHERE date(created_at) <= ?
        """,
        conn,
        params=(date_str,)
    )
    transit_value = int(transit.iloc[0]["total"] or 0)

    # 3 Cash (derived)
    revenue = pd.read_sql(
        """
        SELECT SUM(net_revenue) AS total
        FROM net_sales
        WHERE sale_date <= ?
        """,
        conn,
        params=(date_str,)
    )["total"].iloc[0] or 0

    expenses = pd.read_sql(
        """
        SELECT SUM(amount) AS total
        FROM operating_expenses
        WHERE expense_date <= ?
        """,
        conn,
        params=(date_str,)
    )["total"].iloc[0] or 0

    cash_balance = int(revenue - expenses - transit_value)

    # ----------------------------
    # LIABILITIES (Phase 1)
    # ----------------------------
    liabilities = 0

    # ----------------------------
    # EQUITY
    # ----------------------------
    total_assets = inventory_value + transit_value + cash_balance
    equity = total_assets - liabilities

    conn.close()

    # ============================
    # DISPLAY
    # ============================
    st.markdown("### Assets")

    a1, a2, a3 = st.columns(3)
    a1.metric("Cash (KES)", cash_balance)
    a2.metric("Inventory on Hand (KES)", inventory_value)
    a3.metric("Stock in Transit (KES)", transit_value)

    st.divider()

    st.markdown("### Liabilities")
    st.metric("Total Liabilities (KES)", liabilities)

    st.divider()

    st.markdown("### Equity")
    st.metric("Owners Equity (KES)", equity)

    st.divider()

    # ----------------------------
    # ACCOUNTING CHECK
    # ----------------------------
    st.success(
        f"Assets (KES {total_assets}) = "
        f"Liabilities (KES {liabilities}) + "
        f"Equity (KES {equity})"
    )

    # Optional table
    st.subheader("Balance Sheet Table View")
    bs = pd.DataFrame({
            "Category": [
                "Cash",
                "Inventory (On Hand)",
                "Inventory (In Transit)",
                "Total Assets",
                "Total Liabilities",
                "Owner's Equity"
            ],
            "Amount (KES)": [
                cash_balance,
                inventory_value,
                transit_value,
                total_assets,
                liabilities,
                equity
            ]
        })

    st.dataframe(bs, hide_index=True, use_container_width=True)
    if st.button("Export Balance Sheet as PDF"):
        pdf_path = export_balance_sheet_pdf(
            as_of,
            cash_balance,
            inventory_value,
            transit_value,
            liabilities,
            equity
        )

        with open(pdf_path, "rb") as f:
            st.download_button(
                "Download Balance Sheet (PDF)",
                f,
                file_name="Balance_Sheet.pdf",
                mime="application/pdf"
            )


def export_balance_sheet_pdf(as_of, cash, inventory, transit, liabilities, equity):
    file_path = "/mnt/data/Balance_Sheet.pdf"

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    elements = []

    # ----------------------------
    # TITLE
    # ----------------------------
    elements.append(Paragraph("<b>Shoes Nexus</b>", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(
        Paragraph(
            f"<b>Balance Sheet</b><br/>As at {as_of.strftime('%d %B %Y')}",
            styles["Heading2"]
        )
    )
    elements.append(Spacer(1, 20))

    # ----------------------------
    # ASSETS
    # ----------------------------
    elements.append(Paragraph("<b>ASSETS</b>", styles["Heading3"]))

    assets_table = [
        ["Cash", f"KES {cash:,}"],
        ["Inventory (On Hand)", f"KES {inventory:,}"],
        ["Inventory (In Transit)", f"KES {transit:,}"],
        ["<b>Total Assets</b>", f"<b>KES {cash + inventory + transit:,}</b>"]
    ]

    table = Table(assets_table, colWidths=[260, 200])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT")
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    # ----------------------------
    # LIABILITIES
    # ----------------------------
    elements.append(Paragraph("<b>LIABILITIES</b>", styles["Heading3"]))

    liabilities_table = [
        ["Total Liabilities", f"KES {liabilities:,}"]
    ]

    table = Table(liabilities_table, colWidths=[260, 200])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT")
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    # ----------------------------
    # EQUITY
    # ----------------------------
    elements.append(Paragraph("<b>EQUITY</b>", styles["Heading3"]))

    equity_table = [
        ["Owners Equity", f"KES {equity:,}"]
    ]

    table = Table(equity_table, colWidths=[260, 200])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT")
    ]))
    elements.append(table)
    elements.append(Spacer(1, 30))

    # ----------------------------
    # ACCOUNTING CHECK
    # ----------------------------
    elements.append(
        Paragraph(
            f" Assets = Liabilities + Equity<br/>"
            f"KES {cash + inventory + transit:,} = "
            f"KES {liabilities:,} + KES {equity:,}",
            styles["Normal"]
        )
    )

    doc.build(elements)

    return file_path


# ----------------------------
# ROLE SCREENS
# ----------------------------
def render_stock_take_compliance_gate(role_key):
    month_key = pd.Timestamp.today().strftime("%Y-%m")
    conn = get_db()
    ensure_month_schedule_rows(conn, month_key)
    df = pd.read_sql(
        """
        SELECT
            checkpoint_type,
            due_date,
            completed_at,
            COALESCE(total_products, 0) AS total_products,
            COALESCE(total_units, 0) AS total_units,
            COALESCE(total_value, 0) AS total_value,
            COALESCE(completed_by, '') AS completed_by
        FROM monthly_stock_takes
        WHERE month_key = ?
        ORDER BY due_date ASC
        """,
        conn,
        params=(month_key,),
    )

    if df.empty:
        conn.close()
        st.error("Stock take schedule is unavailable.")
        return False

    today_str = pd.Timestamp.today().strftime("%Y-%m-%d")
    started_set = set(_started_checkpoints_for_date(month_key))
    df["status"] = df.apply(
        lambda r: (
            "COMPLETED"
            if pd.notna(r["completed_at"]) and str(r["completed_at"]).strip() != ""
            else (
                "UPCOMING"
                if str(r["checkpoint_type"]) not in started_set
                else ("OVERDUE" if str(r["due_date"]) < today_str else "PENDING")
            )
        ),
        axis=1,
    )

    required_cp, _ = get_required_checkpoint(conn, month_key)
    if not required_cp:
        conn.close()
        return True

    st.markdown("### Mandatory Stock Take Compliance")
    st.caption(
        f"{month_key}: OPENING (month start), AUDIT_1 (+7 days), AUDIT_2 (+14 days), CLOSING (month end)."
    )

    view = df.rename(
        columns={
            "checkpoint_type": "Checkpoint",
            "due_date": "Due Date",
            "completed_at": "Completed At",
            "total_products": "Total Products",
            "total_units": "Total Units",
            "total_value": "Total Value (KES)",
            "completed_by": "Completed By",
            "status": "Status",
        }
    )
    view["Total Value (KES)"] = view["Total Value (KES)"].map(lambda x: int(float(x or 0)))
    # Keep manager/cashier view lightweight; full totals remain in Monthly Report.
    if str(role_key).lower() in {"manager", "cashier"}:
        lite = view[["Checkpoint", "Due Date", "Completed At", "Status"]].copy()
        st.dataframe(lite, hide_index=True, use_container_width=True)
    else:
        st.dataframe(view, hide_index=True, use_container_width=True)

    # Block only checkpoints that have started for the current date window.
    pending = df[df["status"].isin(["OVERDUE", "PENDING"])]
    if not pending.empty:
        overdue = pending[pending["status"] == "OVERDUE"]
        if not overdue.empty:
            st.error("Access blocked: overdue stock take checkpoints must be completed first.")
        else:
            st.warning("Access blocked: pending stock take checkpoints must be completed first.")
        if st.button("Open Stock Take", key=f"{role_key}_open_stock_take"):
            conn.close()
            st.switch_page("pages/stock_take.py")
        if st.button("Open Monthly Report", key=f"{role_key}_open_monthly_report"):
            conn.close()
            st.switch_page("pages/monthly_report.py")
        conn.close()
        return False

    conn.close()
    return True

def cashier_home():
    render_page_intro("Cashier Workspace", "Sales, brokered deals, inventory lookup, and return requests.")
    sections = ["POS and Sales", "Inventory", "Returns and Exchanges"]
    if st.session_state.get("cashier_section") not in sections:
        st.session_state.cashier_section = "POS and Sales"
    st.radio(
        "Cashier Sections",
        sections,
        horizontal=True,
        key="cashier_section",
        label_visibility="collapsed",
    )
    if st.session_state.cashier_section == "POS and Sales":
        render_section_hint("Sales Entry", "Record product and brokered sales.")
        pos_screen(False)
        render_review_sale_section()
    if st.session_state.cashier_section == "Inventory":
        render_section_hint("Inventory Lookup", "View available products, sizes, and selling prices.")
        inventory_overview("Cashier")
    if st.session_state.cashier_section == "Returns and Exchanges":
        render_section_hint("Returns and Exchanges", "Submit return requests and process exchanges.")
        with st.expander("Returns and Exchanges", expanded=True):
            manager_process_exchange()
            manager_request_return()
            manager_view_return_status()
    if st.button("Logout", key="cashier_logout_main"):
        st.session_state.clear()
        st.rerun()

def manager_home():
    render_page_intro("Manager Workspace", "Sales, inventory, returns, operations, and history tools.")
    if not render_stock_take_compliance_gate("manager"):
        return
    sections = [
        "POS and Sales",
        "Inventory",
        "Stock Operations",
        "Returns Desk",
        "History Tools",
    ]
    if st.session_state.get("manager_section") not in sections:
        st.session_state.manager_section = "POS and Sales"

    st.radio(
        "Manager Sections",
        sections,
        horizontal=True,
        key="manager_section",
        label_visibility="collapsed",
    )

    if st.session_state.manager_section == "POS and Sales":
        render_section_hint("Sales Entry", "Record walk-in and channel sales.")
        pos_screen(True)
        render_review_sale_section()

    if st.session_state.manager_section == "Inventory":
        render_section_hint("Inventory Overview", "Read-only stock visibility by brand, model, color, and size.")
        inventory_overview("Manager")
        st.divider()
        render_section_hint("Stock Alerts", "Monitor low stock and size movement.")
        with st.expander("Stock Alerts and Size Movement", expanded=False):
            stock_alerts()
            zero_size_stock_alerts("Manager")
            size_stock_alerts("Manager")
            most_sold_sizes_per_product()
            most_sold_sizes_by_gender()
            dead_sizes_alerts()
            discount_suggestions()
            slow_sizes_alerts()

    if st.session_state.manager_section == "Stock Operations":
        render_section_hint("Stock Operations", "Use these workflows for all product add and restock changes.")
        with st.expander("Stock Operations", expanded=True):
            stock_operations_panel("Manager")
        with st.expander("Stock In Transit", expanded=False):
            add_stock_in_transit("Manager")
            view_stock_in_transit()
        with st.expander("Operating Expenses", expanded=False):
            operating_expenses_entry()
        with st.expander("Admin Updates", expanded=False):
            manager_view_admin_updates()

    if st.session_state.manager_section == "Returns Desk":
        render_section_hint("Returns Management", "Process exchanges and submit return requests.")
        with st.expander("Returns and Exchanges", expanded=True):
            manager_process_exchange()
            manager_request_return()
            manager_view_return_status()
            manager_view_my_requests()

    if st.session_state.manager_section == "History Tools":
        render_section_hint(
            "History Tools",
            "Requires admin approval before backdated entries are treated as official records.",
        )
        st.warning("Admin approval is required for backdated sales, expenses, or stock entries.")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Backdate Sale", key="manager_backdate_sale", use_container_width=True):
                st.switch_page("pages/backdate_sales.py")
        with c2:
            if st.button("Backdate Expense", key="manager_backdate_expense", use_container_width=True):
                st.switch_page("pages/backdate_expenses.py")
        with c3:
            if st.button("Backdate Stock Additions", key="manager_backdate_stock", use_container_width=True):
                st.switch_page("pages/backdate_stock_additions.py")
    st.divider()
    if st.button("Logout", key="manager_logout_main"):
        st.session_state.clear()
        st.rerun()

def admin_home():
    snapshot = get_today_snapshot()
    render_page_intro("Admin Dashboard", "Manage operations, finance, and audit workflows.")
    render_kpi_row(snapshot, "Admin")
    if not render_stock_take_compliance_gate("admin"):
        return
    sections = [
        "POS and Sales",
        "Inventory",
        "Stock Operations",
        "Analytics",
        "Finance",
        "Returns",
        "Audit and Admin",
    ]
    if st.session_state.get("admin_section") not in sections:
        st.session_state.admin_section = "POS and Sales"
    st.radio(
        "Admin Sections",
        sections,
        horizontal=True,
        key="admin_section",
        label_visibility="collapsed",
    )

    if st.session_state.admin_section == "POS and Sales":
        render_section_hint("Sales Operations", "Run sales operations and verify transaction capture.")
        pos_screen(True)
        render_review_sale_section()

    if st.session_state.admin_section == "Inventory":
        render_section_hint("Inventory Overview", "Read-only stock visibility by brand, model, color, and size.")
        inventory_overview("Admin")
        st.divider()
        render_section_hint("Stock Alerts", "Identify low stock, dead sizes, and valuation gaps.")
        with st.expander("Stock Alerts and Controls", expanded=False):
            stock_alerts()
            zero_size_stock_alerts("Admin")
            size_stock_alerts("Admin")
            slow_sizes_alerts()
            dead_sizes_alerts()
            discount_suggestions()
            inventory_valuation_summary()

    if st.session_state.admin_section == "Stock Operations":
        render_section_hint("Stock Operations", "Use these workflows for all product add, restock, and lifecycle changes.")
        with st.expander("Stock Operations", expanded=True):
            stock_operations_panel("Admin")
        with st.expander("Product Lifecycle", expanded=False):
            admin_archive_restore_product()
        with st.expander("Stock In Transit", expanded=False):
            add_stock_in_transit("Admin")
            view_stock_in_transit()

    if st.session_state.admin_section == "Analytics":
        render_section_hint("Sales Reports", "Review sales performance and size trends.")
        with st.expander("Sales Analytics", expanded=True):
            admin_reports()
        with st.expander("Most Sold Sizes and Trends", expanded=False):
            most_sold_sizes_per_product()
            most_sold_sizes_by_gender()
        with st.expander("Product Audit Filter", expanded=False):
            product_audit_filter()

    if st.session_state.admin_section == "Finance":
        render_section_hint("COGS Control", "Record opening inventory and validate cost of goods.")
        with st.expander("COGS", expanded=False):
            record_opening_inventory()
            cogs_summary()
        render_section_hint("Financial Statements", "Track expenses, profitability, and balance sheet.")
        with st.expander("Financial Statements", expanded=False):
            with st.expander("Record Operating Expense", expanded=True):
                record_operating_expense()
            with st.expander("Operating Expenses Summary", expanded=False):
                operating_expenses_summary()
            with st.expander("Profit and Loss Statement", expanded=False):
                profit_and_loss_statement()
            with st.expander("Balance Sheet", expanded=False):
                balance_sheet()

    if st.session_state.admin_section == "Returns":
        render_section_hint("Returns Management", "Approve or reject requests with full history.")
        with st.expander("Returns and Exchanges", expanded=True):
            manager_process_exchange()
            st.divider()
            admin_handle_exchange_requests()
            st.divider()
            admin_handle_returns()
            admin_monthly_activity_summary()

    if st.session_state.admin_section == "Audit and Admin":
        render_section_hint("Audit and Controls", "Inspect activity logs and run integrity checks.")
        with st.expander("Sale Review Requests", expanded=False):
            admin_handle_sale_review_requests()
        with st.expander("Backdate Approvals", expanded=True):
            admin_handle_backdate_approvals()
        with st.expander("System Activity and Audit Logs", expanded=False):
            admin_view_activity_log()
            st.divider()
            admin_data_integrity_panel()

    if st.button("Logout", key="admin_logout_main"):
        st.session_state.clear()
        st.rerun()



# ----------------------------
# MAIN ROUTER
# ----------------------------
def main():
    st.set_page_config(page_title="Shoes Nexus", layout="wide")

    # ----------------------------
    # SESSION + DB INIT
    # ----------------------------
    init_session()
    ensure_activity_log()
    ensure_staff_security_columns()
    ensure_backdate_approval_requests_table()
    ensure_sale_review_requests_table()
    ensure_product_stock_column()
    ensure_sales_source_column()
    ensure_sales_tracking_columns()
    ensure_sales_checkout_columns()
    ensure_style_catalog_tables()
    ensure_returns_refund_columns()
    ensure_stock_cost_layers_table()
    ensure_product_public_fields()
    ensure_net_sales_view()
    ensure_operating_expenses_table()
    ensure_home_expenses_table()
    normalize_operating_expense_categories()
    ensure_stock_in_transit_table()
    ensure_opening_inventory_table()
    ensure_monthly_stock_takes_table()
    ensure_stock_take_submission_tables()
    reset_mistaken_bulk_stock_take_completions()
    ensure_db_indexes()
    backfill_style_catalog(cutover_date="2026-03-01")
    sync_all_product_stock()
    bootstrap_stock_cost_layers()
    backfill_missing_expense_logs()
    upgrade_stock_in_transit_table()
    upgrade_sales_for_returns()

    # ----------------------------
    # SIDEBAR CSS (STYLE ONLY)
    # ----------------------------
    st.markdown("""
        <style>
        :root {
            --sn-black: #0b0b0f;
            --sn-red: #c41224;
            --sn-red-dark: #9f0918;
            --sn-white: #ffffff;
            --sn-muted: #9aa0aa;
            --sn-surface: #2b0b12;
            --sn-border: #e5e8ef;
        }

        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(1200px circle at 12% -12%, rgba(196,18,36,0.18), transparent 45%),
                radial-gradient(900px circle at 100% 0%, rgba(159,9,24,0.12), transparent 40%),
                linear-gradient(135deg, #f7eef1 0%, #f6edf0 45%, #f3e7eb 100%) !important;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, var(--sn-black) 0%, #13151e 100%);
            border-right: 1px solid rgba(255,255,255,0.08);
        }

        [data-testid="stSidebar"] .stMarkdown,
        [data-testid="stSidebar"] .stMarkdown p,
        [data-testid="stSidebar"] .stMarkdown h1,
        [data-testid="stSidebar"] .stMarkdown h2,
        [data-testid="stSidebar"] .stMarkdown h3,
        [data-testid="stSidebar"] .stMarkdown h4,
        [data-testid="stSidebar"] .stMarkdown h5,
        [data-testid="stSidebar"] .stMarkdown h6,
        [data-testid="stSidebar"] [data-testid="stSidebarNavItems"] {
            color: #f6f7fb !important;
        }

        /* Hide Streamlit default multipage list; use custom role nav only */
        [data-testid="stSidebarNav"] {
            display: none !important;
        }

        .sn-user-panel {
            background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.04));
            border: 1px solid rgba(255,255,255,0.14);
            padding: 0.95rem;
            border-radius: 14px;
            margin-bottom: 1rem;
        }

        .sn-user-name {
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 0.3rem;
        }

        .sn-user-role {
            display: inline-block;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            background: var(--sn-red);
            color: var(--sn-white) !important;
            border-radius: 999px;
            padding: 0.18rem 0.55rem;
        }

        .sn-nav-group {
            margin-top: 0.8rem;
            margin-bottom: 0.35rem;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #cdd2dc !important;
        }

        [data-testid="stSidebar"] .stButton {
            width: 100%;
        }

        [data-testid="stSidebar"] .stButton > button {
            width: 100%;
            display: block;
            text-align: left;
            background: var(--sn-white);
            color: #151821 !important;
            border: 1px solid var(--sn-border);
            border-radius: 12px;
            padding: 0.62rem 0.85rem;
            margin-bottom: 0.45rem;
            font-weight: 600;
            transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
        }

        [data-testid="stSidebar"] .stButton > button * {
            color: #151821 !important;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            transform: translateY(-1px);
            border-color: #f0b6bc;
            box-shadow: 0 10px 24px rgba(11,11,15,0.08);
        }

        [data-testid="stSidebar"] .stButton > button:focus-visible {
            outline: 2px solid var(--sn-red);
            outline-offset: 2px;
        }

        .sn-page-hero {
            border: 1px solid var(--sn-border);
            border-radius: 18px;
            padding: 0.72rem 0.9rem;
            margin-bottom: 0.58rem;
            background: #ffffff;
            box-shadow: 0 8px 18px rgba(11,11,15,0.04);
        }

        .sn-page-hero h1 {
            margin: 0;
            font-size: 1.45rem;
            line-height: 1.2;
            color: #12141b;
        }

        .sn-hero-head {
            display: flex;
            align-items: center;
            justify-content: flex-start;
            gap: 0.45rem;
        }

        .sn-hero-logo {
            flex: 0 0 auto;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .sn-hero-logo img {
            width: 100px;
            height: auto;
            object-fit: contain;
        }

        .sn-page-hero p {
            margin: 0.24rem 0 0 0;
            color: #5e6572;
            font-size: 0.9rem;
        }

        .sn-pos-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.7rem;
            margin: 0 0 .5rem 0;
        }

        .sn-pos-head h2 {
            margin: 0;
            color: #0b0b0f;
            font-weight: 800;
            font-size: 3rem;
            line-height: 1.1;
        }

        .sn-pos-logo {
            flex: 0 0 auto;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .sn-pos-logo img {
            width: 94px;
            height: auto;
            object-fit: contain;
        }

        .sn-kpi-row {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.65rem;
            margin: 0.6rem 0 1rem 0;
        }

        .sn-kpi-card {
            border: 1px solid var(--sn-border);
            border-radius: 14px;
            padding: 0.75rem 0.8rem;
            background: #fff;
            box-shadow: 0 10px 22px rgba(11,11,15,0.05);
        }

        .sn-kpi-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #646b78;
            font-weight: 700;
        }

        .sn-kpi-value {
            margin-top: 0.25rem;
            font-size: 1.15rem;
            color: #10121a;
            font-weight: 800;
        }

        .sn-kpi-note {
            margin-top: 0.2rem;
            font-size: 0.74rem;
            color: #747b88;
        }

        .sn-login-wrap {
            border: 1px solid var(--sn-border);
            border-radius: 16px;
            background: #fff;
            box-shadow: 0 16px 36px rgba(11,11,15,0.08);
            padding: 0.95rem;
            margin-bottom: 0.7rem;
            max-width: 520px;
        }

        .sn-auth-hero {
            max-width: 980px;
            margin: 0.2rem auto 0.6rem auto;
        }
        .sn-auth-title-row {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            justify-content: center;
            width: 100%;
        }
        .sn-auth-title-row h1 {
            margin: 0;
        }
        .sn-auth-hero-logo {
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }
        .sn-auth-hero-logo img {
            width: 88px;
            height: auto;
            object-fit: contain;
        }

        .sn-auth-shell {
            display: flex;
            justify-content: center;
            width: 100%;
            margin: 0.25rem 0 0.8rem 0;
        }

        .sn-auth-card {
            width: min(580px, 100%);
            border: 1px solid var(--sn-border);
            border-radius: 16px;
            background: #ffffff;
            box-shadow: 0 16px 34px rgba(11,11,15,0.07);
            padding: 1rem 1rem 0.9rem 1rem;
        }

        .sn-auth-card .stButton > button {
            width: 100%;
            margin-top: 0.25rem;
        }

        .sn-section-hint {
            border: 1px dashed #d4d8e1;
            border-radius: 12px;
            background: #fcfcfe;
            padding: 0.62rem 0.8rem;
            margin: 0.45rem 0 0.55rem 0;
        }

        .sn-section-hint-title {
            font-size: 0.8rem;
            font-weight: 800;
            color: #202430;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 0.15rem;
        }

        .sn-section-hint-text {
            font-size: 0.82rem;
            color: #5f6673;
            line-height: 1.35;
        }

        [data-testid="stExpander"] {
            border: 1px solid var(--sn-border);
            border-radius: 14px;
            background: #ffffff;
            box-shadow: 0 10px 24px rgba(11,11,15,0.04);
            margin-bottom: 0.65rem;
            overflow: hidden;
        }

        [data-testid="stExpander"] summary {
            background: linear-gradient(180deg, #fff, #f8f9fc);
            font-weight: 700;
            color: #202430;
        }

        [data-testid="stExpander"] [data-testid="stMarkdownContainer"] p {
            color: #28303b;
        }

        .stTextInput > div > div > input,
        .stNumberInput > div > div > input,
        .stTextArea textarea,
        .stSelectbox [data-baseweb="select"] > div,
        .stMultiSelect [data-baseweb="select"] > div,
        .stDateInput > div > div > input {
            border-radius: 12px !important;
            border: 1px solid #d7dce6 !important;
            background: #ffffff !important;
            color: #151821 !important;
            -webkit-text-fill-color: #151821 !important;
            box-shadow: inset 0 0 0 1px rgba(255,255,255,0.25);
        }

        /* Date input: enforce readable text/background in all states */
        .stDateInput [data-baseweb="input"] {
            background: #ffffff !important;
            border: 1px solid #d7dce6 !important;
            border-radius: 12px !important;
        }

        .stDateInput [data-baseweb="input"] input {
            color: #111318 !important;
            -webkit-text-fill-color: #111318 !important;
            background: #ffffff !important;
            opacity: 1 !important;
            font-weight: 600;
        }

        .stDateInput [data-baseweb="input"] input::placeholder {
            color: #7a8291 !important;
            -webkit-text-fill-color: #7a8291 !important;
            opacity: 1 !important;
        }

        .stDateInput [data-baseweb="input"] svg,
        .stDateInput svg {
            fill: #111318 !important;
            color: #111318 !important;
            opacity: 1 !important;
        }

        /* Force strong contrast for selectbox values and dropdown options */
        .stSelectbox [data-baseweb="select"] * {
            color: #111318 !important;
            -webkit-text-fill-color: #111318 !important;
            opacity: 1 !important;
        }

        [data-baseweb="popover"] [role="listbox"] *,
        [data-baseweb="popover"] [role="option"] *,
        div[role="listbox"] *,
        div[role="option"] * {
            color: #111318 !important;
            -webkit-text-fill-color: #111318 !important;
            opacity: 1 !important;
        }

        [data-baseweb="popover"] [role="listbox"],
        [data-baseweb="popover"] [role="option"] {
            background: #ffffff !important;
        }

        .stSelectbox svg,
        .stMultiSelect svg {
            fill: #111318 !important;
            color: #111318 !important;
            opacity: 1 !important;
        }

        .stNumberInput [data-baseweb="input"] {
            background: #ffffff !important;
            border: 1px solid #d7dce6 !important;
            border-radius: 12px !important;
        }

        .stNumberInput [data-baseweb="input"] input {
            color: #111318 !important;
            -webkit-text-fill-color: #111318 !important;
            background: #ffffff !important;
            font-weight: 700;
            opacity: 1 !important;
        }

        .stNumberInput [data-baseweb="input"] button,
        .stNumberInput [data-baseweb="input"] [role="button"] {
            background: #ffffff !important;
            color: #111318 !important;
            -webkit-text-fill-color: #111318 !important;
            opacity: 1 !important;
        }

        .stTextInput > div > div > input::placeholder,
        .stNumberInput > div > div > input::placeholder,
        .stTextArea textarea::placeholder,
        .stDateInput > div > div > input::placeholder {
            color: #7a8291 !important;
            opacity: 1 !important;
        }

        /* Date picker popup readability */
        [data-baseweb="calendar"],
        [data-baseweb="calendar"] * {
            color: #111318 !important;
            -webkit-text-fill-color: #111318 !important;
            opacity: 1 !important;
        }

        [data-baseweb="calendar"] {
            background: #ffffff !important;
            border: 1px solid #d7dce6 !important;
            border-radius: 12px !important;
        }

        /* Normalize calendar header/nav surfaces to avoid dark-on-dark text */
        [data-baseweb="calendar"] button,
        [data-baseweb="calendar"] select,
        [data-baseweb="calendar"] [role="button"] {
            background: #ffffff !important;
            color: #111318 !important;
            -webkit-text-fill-color: #111318 !important;
        }

        [data-baseweb="calendar"] [aria-selected="true"],
        [data-baseweb="calendar"] [aria-selected="true"] * {
            background: #c41224 !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }

        [data-testid="stWidgetLabel"] label,
        [data-testid="stWidgetLabel"] p,
        [data-testid="stWidgetLabel"] label p,
        .sn-login-wrap [data-testid="stMarkdownContainer"] p {
            color: #2b3240 !important;
            font-weight: 600;
        }

        .st-key-login_username [data-testid="stWidgetLabel"] *,
        .st-key-login_password [data-testid="stWidgetLabel"] * {
            color: #2b3240 !important;
            font-weight: 600;
        }

        .stTextInput > div > div > input:focus,
        .stNumberInput > div > div > input:focus,
        .stTextArea textarea:focus {
            border-color: var(--sn-red) !important;
            box-shadow: 0 0 0 2px rgba(196,18,36,0.15) !important;
        }

        [data-testid="stMetricValue"] {
            color: #171a22;
            font-weight: 800;
        }

        [data-testid="stMetricLabel"] {
            color: #5d6472;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            font-size: 0.72rem;
            font-weight: 700;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--sn-border);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 10px 24px rgba(11,11,15,0.05);
        }

        [data-testid="stDataFrame"] *,
        [data-testid="stTable"] *,
        .stDataFrame *,
        .stTable * {
            color: #111318 !important;
            opacity: 1 !important;
        }

        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stMarkdownContainer"] strong,
        [data-testid="stMarkdownContainer"] span {
            color: #151821 !important;
            opacity: 1 !important;
        }

        .stSubheader,
        .stSubheader *,
        h2, h3, h4 {
            color: #10131a !important;
            opacity: 1 !important;
            font-weight: 800 !important;
        }

        .stCaption,
        .stCaption * {
            color: #394151 !important;
            opacity: 1 !important;
        }

        [data-testid="stAlert"] {
            border-radius: 12px;
            border: 1px solid #e1e6ef;
            background: #ffffff !important;
        }

        [data-testid="stAlert"] *,
        [data-testid="stAlert"] p,
        [data-testid="stAlert"] span,
        [data-testid="stAlert"] div {
            color: #111318 !important;
            opacity: 1 !important;
            font-weight: 600;
        }

        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary *,
        [data-testid="stExpanderDetails"] *,
        [data-testid="stExpanderDetails"] p,
        [data-testid="stExpanderDetails"] span,
        [data-testid="stExpanderDetails"] li {
            color: #111318 !important;
            opacity: 1 !important;
        }

        [data-testid="stExpander"] summary {
            font-weight: 700 !important;
        }

        [data-baseweb="tab-list"] {
            gap: 0.35rem;
            margin-bottom: 0.55rem;
        }

        [data-baseweb="tab"] {
            border-radius: 10px;
            border: 1px solid #d9dde7;
            background: #ffffff;
            color: #28303b;
            padding: 0.35rem 0.72rem;
            font-weight: 600;
            transition: all 0.18s ease;
        }

        [data-baseweb="tab"]:hover {
            border-color: #f0b6bc;
            color: #1c212c;
        }

        [aria-selected="true"][data-baseweb="tab"] {
            background: var(--sn-black);
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            border-color: var(--sn-black);
        }

        [aria-selected="true"][data-baseweb="tab"] * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            opacity: 1 !important;
        }

        .stRadio [role="radiogroup"] {
            display: flex;
            flex-wrap: wrap;
            gap: 0.42rem;
            margin-bottom: 0.55rem;
        }

        .stRadio [role="radiogroup"] label {
            background: #ffffff;
            border: 1px solid #d9dde7;
            border-radius: 10px;
            padding: 0.35rem 0.72rem;
            margin: 0 !important;
        }

        .stRadio [role="radiogroup"] label p {
            color: #28303b !important;
            font-weight: 600;
            margin: 0 !important;
        }

        .stRadio [role="radiogroup"] label:has(input:checked) {
            background: var(--sn-black);
            border-color: var(--sn-black);
        }

        .stRadio [role="radiogroup"] label:has(input:checked) p {
            color: #ffffff !important;
        }

        [data-testid="stMain"] .stButton > button,
        [data-testid="stMain"] .stFormSubmitButton > button,
        [data-testid="stMain"] .stDownloadButton > button {
            background: var(--sn-black) !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            border: 1px solid var(--sn-black) !important;
            font-weight: 700 !important;
        }

        [data-testid="stMain"] .stButton > button *,
        [data-testid="stMain"] .stFormSubmitButton > button *,
        [data-testid="stMain"] .stDownloadButton > button * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            opacity: 1 !important;
        }

        [data-testid="stMain"] [data-testid="baseButton-primary"],
        [data-testid="stMain"] [data-testid="baseButton-secondary"],
        [data-testid="stMain"] [data-testid="baseButton-primary"] *,
        [data-testid="stMain"] [data-testid="baseButton-secondary"] * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            opacity: 1 !important;
        }

        [data-testid="stMain"] [data-testid="baseButton-primary"] svg,
        [data-testid="stMain"] [data-testid="baseButton-secondary"] svg,
        [data-testid="stMain"] .stDownloadButton svg {
            fill: #ffffff !important;
            color: #ffffff !important;
            opacity: 1 !important;
        }

        [data-testid="stMain"] [data-testid="baseButton-primary"]:disabled,
        [data-testid="stMain"] [data-testid="baseButton-secondary"]:disabled,
        [data-testid="stMain"] [data-testid="baseButton-primary"]:disabled *,
        [data-testid="stMain"] [data-testid="baseButton-secondary"]:disabled * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            opacity: 0.7 !important;
        }

        [data-testid="stMain"] .stButton > button:hover,
        [data-testid="stMain"] .stFormSubmitButton > button:hover,
        [data-testid="stMain"] .stDownloadButton > button:hover {
            background: var(--sn-red-dark) !important;
            border-color: var(--sn-red-dark) !important;
        }

        [data-testid="stHorizontalBlock"] [data-testid="baseButton-secondary"] {
            border-radius: 10px !important;
        }

        .sn-login-wrap .stButton > button {
            width: 100%;
            border-radius: 12px;
            background: var(--sn-black);
            color: var(--sn-white);
            border: 1px solid var(--sn-black);
            font-weight: 700;
            padding: 0.62rem 0.8rem;
        }

        .sn-login-wrap .stButton > button:hover {
            background: var(--sn-red-dark);
            border-color: var(--sn-red-dark);
        }

        .st-key-login_submit button {
            width: 100%;
            border-radius: 12px;
            background: var(--sn-black);
            color: var(--sn-white);
            border: 1px solid var(--sn-black);
            font-weight: 700;
            padding: 0.62rem 0.8rem;
        }

        .st-key-login_submit button:hover {
            background: var(--sn-red-dark);
            border-color: var(--sn-red-dark);
        }

        @media (max-width: 1200px) {
            .sn-kpi-row {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 900px) {
            [data-testid="stHorizontalBlock"] {
                flex-direction: column !important;
            }
            [data-testid="stHorizontalBlock"] > div {
                width: 100% !important;
            }
            [data-testid="stMain"] .stButton > button,
            [data-testid="stMain"] .stFormSubmitButton > button,
            [data-testid="stMain"] .stDownloadButton > button {
                width: 100% !important;
            }
        }

        @media (max-width: 640px) {
            .sn-page-hero {
                padding: 0.82rem 0.9rem;
            }

            .sn-page-hero h1 {
                font-size: 1.22rem;
            }

            .sn-hero-head {
                gap: 0.45rem;
            }

            .sn-hero-logo img {
                width: 72px;
            }

            .sn-auth-hero {
                margin-bottom: 0.7rem;
            }
            .sn-auth-hero-logo img {
                width: 64px;
            }

            .sn-pos-head h2 {
                font-size: 2.2rem;
            }

            .sn-pos-logo img {
                width: 72px;
            }

            .sn-auth-card {
                padding: 0.85rem 0.8rem 0.8rem 0.8rem;
            }

            .sn-kpi-row {
                grid-template-columns: 1fr;
            }
        }
        </style>
    """, unsafe_allow_html=True)

    # ============================================
    # CHECK IF LOGGED IN
    # ============================================
    if st.session_state.logged_in:
        auto_logout()

        # ============================================
        # SIDEBAR (ONLY ONE PLACE)
        # ============================================
        with st.sidebar:
            st.markdown(f"""
                <div class="sn-user-panel">
                    <div class="sn-user-name">{st.session_state.username}</div>
                    <div class="sn-user-role">{st.session_state.role}</div>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("### Navigation")
            render_sidebar_navigation(st.session_state.role)

            st.markdown("---")

            if st.button("Logout", key="sidebar_logout"):
                st.session_state.clear()
                st.rerun()

        # ============================================
        # MAIN CONTENT AREA
        # ============================================
        if st.session_state.role == "Cashier":
            cashier_home()
        elif st.session_state.role == "Manager":
            manager_home()
        elif st.session_state.role == "Admin":
            admin_home()
        else:
            st.error("Unknown role")

    else:
        login_screen()


main()






