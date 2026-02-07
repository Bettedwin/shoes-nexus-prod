from db_config import DB_PATH
import streamlit as st
import sqlite3
from datetime import date

# ============================================
# DATABASE CONNECTION
# ============================================
def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# ============================================
# PAGE SETUP
# ============================================
st.set_page_config(page_title="Backdate Expenses", layout="wide")
st.title("📉 Backdate Historical Expenses")

# ============================================
# ACCESS CONTROL
# ============================================
if "role" not in st.session_state or st.session_state.role not in ["Admin", "Manager"]:
    st.error("⛔ Access Denied - Admin or Manager role required")
    st.stop()

st.info("ℹ️ Use this module to record historical expenses")

# ============================================
# STEP 1: DATE SELECTION
# ============================================
st.subheader("Step 1: Select Expense Date")

expense_date = st.date_input(
    "Expense Date",
    value=date.today(),
    max_value=date.today(),
    help="Cannot select future dates"
)

st.write(f"📅 Selected date: **{expense_date}**")

# ============================================
# STEP 2: EXPENSE DETAILS
# ============================================
st.subheader("Step 2: Expense Details")

# Expense categories for easier tracking
expense_category = st.selectbox(
    "Expense Category",
    [
        "Ads Spend",
        "Facebook Ads",
        "Instagram Ads",
        "Google Ads",
        "TikTok Ads",
        "Rent",
        "Utilities",
        "Transportation",
        "Packaging Materials",
        "Other"
    ]
)

# If "Other" is selected, allow custom description
if expense_category == "Other":
    description = st.text_input(
        "Description",
        placeholder="Describe the expense..."
    )
else:
    description = expense_category
    # Allow adding more details
    additional_notes = st.text_input(
        "Additional Notes (optional)",
        placeholder="Add more details if needed..."
    )
    if additional_notes:
        description = f"{expense_category} - {additional_notes}"

amount = st.number_input(
    "Amount (KES)",
    min_value=1,
    step=1,
    help="Enter the expense amount in Kenya Shillings"
)

# ============================================
# STEP 3: REVIEW & SUBMIT
# ============================================
st.subheader("Step 3: Review & Submit")

st.info(f"""
**Expense Summary:**
- Date: {expense_date}
- Category: {expense_category}
- Description: {description}
- Amount: KES {amount:,}
""")

if st.button("💾 Record Expense", type="primary"):
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # Insert expense
        cur.execute("""
            INSERT INTO daily_expenses (amount, description, expense_date)
            VALUES (?, ?, ?)
        """, (int(amount), description, str(expense_date)))
        
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
            f"Backdated expense on {expense_date}: KES {amount:,} - {description}"
        ))
        
        conn.commit()
        
        st.success("✅ Expense recorded successfully!")
        st.balloons()
        
    except Exception as e:
        conn.rollback()
        st.error(f"❌ Error recording expense: {e}")
    finally:
        conn.close()