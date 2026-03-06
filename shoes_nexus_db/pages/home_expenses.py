from datetime import datetime
import sqlite3

import pandas as pd
import streamlit as st

from db_config import DB_PATH
from theme_admin import apply_admin_theme
from ui_feedback import show_success_summary


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_home_expenses_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS home_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date DATE NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def log_activity(event_type, reference_id, message):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO activity_log
        (event_type, reference_id, role, username, message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            event_type,
            int(reference_id),
            st.session_state.get("role", "Admin"),
            st.session_state.get("username", "admin"),
            message,
        ),
    )
    conn.commit()
    conn.close()


def load_recent_expenses(limit=200):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, expense_date, category, description, amount, created_by, created_at
        FROM home_expenses
        ORDER BY expense_date DESC, id DESC
        LIMIT ?
        """,
        (int(limit),),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def render_add_expense():
    st.subheader("Add Home Expense")
    if st.session_state.get("home_add_flash"):
        saved = st.session_state.get("home_add_last_saved", {})
        show_success_summary(
            "Home Expense record saved",
            [
                ("Date", saved.get("expense_date", "")),
                ("Category", saved.get("category", "")),
                ("Description", saved.get("description", "")),
                ("Amount (KES)", f"{int(saved.get('amount', 0)):,}"),
                ("Expense ID", f"#{saved.get('expense_id', '')}"),
            ],
        )
        st.session_state.home_add_flash = False

    c1, c2 = st.columns(2)
    with c1:
        expense_date = st.date_input("Expense Date", pd.Timestamp.today(), key="home_add_date")
    with c2:
        category = st.selectbox(
            "Category",
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
                "Other",
            ],
            key="home_add_category",
        )
    description = st.text_area("Description", key="home_add_description", placeholder="Optional notes")
    amount = st.number_input("Amount (KES)", min_value=0, step=100, key="home_add_amount")

    if st.button("Save Home Expense", key="home_add_submit"):
        if int(amount) <= 0:
            st.error("Amount must be greater than 0.")
            return
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
                category.strip(),
                (description or category).strip(),
                int(amount),
                st.session_state.get("username", "admin"),
            ),
        )
        new_id = int(cur.lastrowid)
        conn.commit()
        conn.close()
        log_activity("HOME_EXPENSE", new_id, f"Home expense: {category} - KES {int(amount)}")
        st.session_state.home_add_last_saved = {
            "expense_id": int(new_id),
            "expense_date": expense_date.strftime("%Y-%m-%d"),
            "category": category.strip(),
            "description": (description or category).strip(),
            "amount": int(amount),
        }
        st.session_state.home_add_flash = True
        st.rerun()


def render_edit_delete():
    st.subheader("Edit or Delete Home Expense")
    rows = load_recent_expenses()
    if not rows:
        st.info("No home expenses to edit yet.")
        return

    by_id = {int(r[0]): r for r in rows}
    option_ids = [int(r[0]) for r in rows]

    def _expense_label(r):
        rid, expense_date, category, description, amount, created_by, created_at = r
        desc_short = (description or "").strip()
        if len(desc_short) > 42:
            desc_short = desc_short[:39] + "..."
        return (
            f"#{rid} | {expense_date} | {category} | KES {int(amount)} | "
            f"{desc_short} | created {created_at}"
        )

    selected_id = st.selectbox(
        "Select home expense",
        option_ids,
        key="home_edit_select",
        format_func=lambda rid: _expense_label(by_id[int(rid)]),
    )
    selected = by_id[int(selected_id)]
    selected_id, orig_date, orig_category, orig_desc, orig_amount, _, _ = selected

    st.caption(f"Selected row ID: {selected_id}")

    col1, col2 = st.columns(2)
    with col1:
        edit_date = st.date_input("Expense Date (edit)", pd.to_datetime(orig_date), key="home_edit_date")
        edit_category = st.text_input("Category (edit)", str(orig_category or ""), key="home_edit_category")
    with col2:
        edit_description = st.text_input("Description (edit)", str(orig_desc or ""), key="home_edit_description")
        edit_amount = st.number_input(
            "Amount (KES) (edit)", min_value=0, step=100, value=int(orig_amount), key="home_edit_amount"
        )

    # Duplicate warning preview before update.
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id
        FROM home_expenses
        WHERE expense_date = ?
          AND category = ?
          AND description = ?
          AND amount = ?
          AND id <> ?
        LIMIT 1
        """,
        (
            edit_date.strftime("%Y-%m-%d"),
            edit_category.strip(),
            edit_description.strip(),
            int(edit_amount),
            int(selected_id),
        ),
    )
    dup_row = cur.fetchone()
    conn.close()

    if dup_row:
        st.warning(
            f"Potential duplicate detected: this would match existing row #{int(dup_row[0])}. "
            "Use caution before updating."
        )
        allow_duplicate_update = st.checkbox(
            "I understand this may create a duplicate-looking record.",
            key="home_edit_allow_duplicate",
        )
    else:
        allow_duplicate_update = True

    u1, u2 = st.columns(2)
    with u1:
        if st.button("Update Home Expense", key="home_edit_submit"):
            if int(edit_amount) <= 0:
                st.error("Amount must be greater than 0.")
                return
            if not allow_duplicate_update:
                st.error("Confirm duplicate warning before updating.")
                return
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE home_expenses
                SET expense_date = ?, category = ?, description = ?, amount = ?
                WHERE id = ?
                """,
                (
                    edit_date.strftime("%Y-%m-%d"),
                    edit_category.strip(),
                    edit_description.strip(),
                    int(edit_amount),
                    int(selected_id),
                ),
            )
            conn.commit()
            conn.close()
            log_activity(
                "HOME_EXPENSE_UPDATED",
                int(selected_id),
                (
                    f"Updated home expense #{selected_id}: "
                    f"date {orig_date}->{edit_date.strftime('%Y-%m-%d')}, "
                    f"category {orig_category}->{edit_category.strip()}, "
                    f"amount {int(orig_amount)}->{int(edit_amount)}"
                ),
            )
            show_success_summary(
                "Home expense updated.",
                [
                    ("Expense ID", int(selected_id)),
                    ("Date", edit_date.strftime("%Y-%m-%d")),
                    ("Category", edit_category.strip()),
                    ("Amount (KES)", f"{int(edit_amount):,}"),
                ],
            )
            st.rerun()

    with u2:
        st.text_input(
            "Type DELETE to enable deletion",
            key="home_delete_confirm_text",
            placeholder="DELETE",
        )
        if st.button("Delete Home Expense", key="home_delete_submit"):
            confirm_text = str(st.session_state.get("home_delete_confirm_text", "")).strip().upper()
            if confirm_text != "DELETE":
                st.error("Deletion confirmation text is required.")
                return
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM home_expenses WHERE id = ?", (int(selected_id),))
            deleted = int(cur.rowcount or 0)
            conn.commit()
            conn.close()
            if deleted:
                log_activity(
                    "HOME_EXPENSE_DELETED",
                    int(selected_id),
                    f"Deleted home expense #{selected_id}: {orig_category} - KES {int(orig_amount)}",
                )
                show_success_summary(
                    "Home expense deleted.",
                    [
                        ("Expense ID", int(selected_id)),
                        ("Category", str(orig_category)),
                        ("Amount (KES)", f"{int(orig_amount):,}"),
                    ],
                )
                st.rerun()
            st.error("No row deleted; it may have already been removed.")


def render_summary():
    st.subheader("Home Expenses Summary")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT MIN(expense_date), MAX(expense_date) FROM home_expenses")
    bounds = cur.fetchone() or (None, None)
    conn.close()

    if not bounds[0] or not bounds[1]:
        st.info("No home expenses recorded yet.")
        return

    min_date = pd.to_datetime(bounds[0]).date()
    max_date = pd.to_datetime(bounds[1]).date()

    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input(
            "From Date",
            min_date,
            key="home_summary_start",
        )
    with c2:
        end_date = st.date_input("To Date", max_date, key="home_summary_end")

    if start_date > end_date:
        st.warning("From Date cannot be after To Date.")
        return

    conn = get_db()
    df = pd.read_sql(
        """
        SELECT id, expense_date, category, description, amount, created_by, created_at
        FROM home_expenses
        WHERE expense_date BETWEEN ? AND ?
        ORDER BY expense_date DESC, id DESC
        """,
        conn,
        params=(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
    )
    conn.close()

    if df.empty:
        st.info("No home expenses in selected range.")
        return

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    st.metric("Total Home Expenses (KES)", int(df["amount"].sum()))
    st.dataframe(df, hide_index=True, use_container_width=True)


def main():
    st.set_page_config(page_title="Home Expenses", layout="wide")
    apply_admin_theme(
        "Home Expenses",
        "Private personal expenses. Kept separate from investor-facing business finance views.",
    )

    if not st.session_state.get("logged_in"):
        st.warning("Session expired. Please log in again.")
        if st.button("Go to Login", key="home_expenses_go_login"):
            st.switch_page("app.py")
        st.stop()

    if st.session_state.get("role") != "Admin":
        st.error("Admin access only.")
        if st.button("Go to Login", key="home_expenses_not_admin_login"):
            st.switch_page("app.py")
        st.stop()

    ensure_home_expenses_table()

    tab_add, tab_manage, tab_summary = st.tabs(["Add Expense", "Edit/Delete", "Summary"])
    with tab_add:
        render_add_expense()
    with tab_manage:
        render_edit_delete()
    with tab_summary:
        render_summary()


main()
