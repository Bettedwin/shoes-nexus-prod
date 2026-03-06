from db_config import DB_PATH
import streamlit as st
import sqlite3
from datetime import date, timedelta
import json
from theme_admin import apply_admin_theme, now_nairobi_str
from ui_feedback import show_success_summary

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

def ensure_operating_expenses_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS operating_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date DATE NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            created_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()

def reset_backdate_expense_form_state():
    st.session_state["bdexp_date"] = date.today()
    st.session_state["bdexp_category"] = OPERATING_EXPENSE_VOTEHEADS[0]
    st.session_state["bdexp_other_description"] = ""
    st.session_state["bdexp_additional_notes"] = ""
    st.session_state["bdexp_amount"] = 1

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

# ============================================
# PAGE SETUP
# ============================================
st.set_page_config(page_title="Backdate Expenses", layout="wide")
apply_admin_theme(
    "Backdate Expenses",
    "Record approved historical expense entries.",
)

if not st.session_state.get("logged_in", False):
    st.warning("Session expired. Please log in again.")
    if st.button("Go to Login", key="backdate_expenses_go_login"):
        st.switch_page("app.py")
    st.stop()

# ============================================
# ACCESS CONTROL
# ============================================
if "role" not in st.session_state or st.session_state.role not in ["Admin", "Manager"]:
    st.error("⛔ Access Denied - Admin or Manager role required")
    st.stop()

ensure_backdate_approval_table()
ensure_operating_expenses_table()

render_theme_notice("Use this module to record historical expenses.")

# ============================================
# STEP 1: DATE SELECTION
# ============================================
st.subheader("Step 1: Select Expense Date")

expense_date = st.date_input(
    "Expense Date",
    value=date.today() - timedelta(days=1),
    max_value=date.today() - timedelta(days=1),
    help="Backdate must be before today.",
    key="bdexp_date",
)

st.write(f"📅 Selected date: **{expense_date}**")

# ============================================
# STEP 2: EXPENSE DETAILS
# ============================================
st.subheader("Step 2: Expense Details")

# Expense categories for easier tracking
expense_category = st.selectbox(
    "Expense Category",
    OPERATING_EXPENSE_VOTEHEADS,
    key="bdexp_category",
)

# If "Other" is selected, allow custom description
if expense_category == "Other":
    description = st.text_input(
        "Description",
        placeholder="Describe the expense...",
        key="bdexp_other_description",
    )
else:
    description = expense_category
    # Allow adding more details
    additional_notes = st.text_input(
        "Additional Notes (optional)",
        placeholder="Add more details if needed...",
        key="bdexp_additional_notes",
    )
    if additional_notes:
        description = f"{expense_category} - {additional_notes}"

amount = st.number_input(
    "Amount (KES)",
    min_value=1,
    step=1,
    help="Enter the expense amount in Kenya Shillings",
    key="bdexp_amount",
)

# ============================================
# STEP 3: REVIEW & SUBMIT
# ============================================
st.subheader("Step 3: Review & Submit")

st.markdown(
    (
        "<div style='background:#fff7f8;border:1px solid #f5c2c7;border-left:4px solid #c41224;"
        "border-radius:12px;padding:12px 14px;margin:8px 0 12px 0;color:#141821;'>"
        "<div style='font-weight:800;margin-bottom:8px;'>Expense Summary</div>"
        f"<div><strong>Date:</strong> {expense_date}</div>"
        f"<div><strong>Category:</strong> {expense_category}</div>"
        f"<div><strong>Description:</strong> {description}</div>"
        f"<div><strong>Amount:</strong> KES {amount:,}</div>"
        "</div>"
    ),
    unsafe_allow_html=True,
)

if st.button("💾 Record Expense", type="primary"):
    if expense_date >= date.today():
        st.error("❌ Backdate must be before today.")
        st.stop()
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        if st.session_state.role == "Manager":
            payload = {
                "expense_date": str(expense_date),
                "expense_category": str(expense_category),
                "description": str(description),
                "amount": int(amount),
            }
            cur.execute(
                """
                INSERT INTO backdate_approval_requests
                (request_type, payload_json, status, requested_by, requested_role)
                VALUES (?, ?, 'PENDING', ?, ?)
                """,
                (
                    "BACKDATE_EXPENSE",
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
                    "BACKDATE_EXPENSE_REQUEST",
                    request_id,
                    st.session_state.role,
                    st.session_state.username,
                    f"Submitted backdated expense request for admin approval. Effective date: {expense_date}. Amount: KES {amount:,}. Submitted at: {now_nairobi_str()}",
                ),
            )
            conn.commit()
            show_success_summary(
                "Request submitted for admin approval.",
                [
                    ("Request ID", f"#{request_id}"),
                    ("Type", "Backdated expense"),
                    ("Date", str(expense_date)),
                    ("Amount (KES)", f"{int(amount):,}"),
                ],
            )
            st.stop()

        # Insert expense
        cur.execute("""
            INSERT INTO operating_expenses (expense_date, category, description, amount, created_by)
            VALUES (?, ?, ?, ?, ?)
        """, (
            str(expense_date),
            str(expense_category),
            description,
            int(amount),
            st.session_state.get("username", "system")
        ))
        
        expense_id = cur.lastrowid
        
        # Activity log
        cur.execute("""
            INSERT INTO activity_log
            (event_type, reference_id, role, username, message)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "BACKDATE_EXPENSE",
            expense_id,
            st.session_state.role,
            st.session_state.username,
            f"Backdated expense recorded. Effective date: {expense_date}. Amount: KES {amount:,}. Details: {description}. Logged at: {now_nairobi_str()}"
        ))
        
        conn.commit()
        
        show_success_summary(
            "Expense recorded successfully.",
            [
                ("Expense ID", int(expense_id)),
                ("Date", str(expense_date)),
                ("Category", str(expense_category)),
                ("Amount (KES)", f"{int(amount):,}"),
                ("Description", str(description or "-")),
            ],
        )
                
    except Exception as e:
        conn.rollback()
        st.error(f"❌ Error recording expense: {e}")
    finally:
        conn.close()
