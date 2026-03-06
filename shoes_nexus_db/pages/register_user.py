from datetime import datetime
import time
import sqlite3

import pandas as pd
import streamlit as st

from db_config import DB_PATH
from security import hash_password, verify_password
from theme_admin import apply_admin_theme
from ui_feedback import show_success_summary


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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
    conn.commit()
    conn.close()


def ensure_staff_management_columns():
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


def log_activity(cur, event_type, reference_id, message):
    cur.execute(
        """
        INSERT INTO activity_log (event_type, reference_id, role, username, message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            str(event_type),
            reference_id,
            str(st.session_state.get("role", "Admin")),
            str(st.session_state.get("username", "admin")),
            str(message),
        ),
    )

def admin_reauth_active() -> bool:
    return float(st.session_state.get("admin_reauth_until", 0)) > time.time()


def require_admin_reauth() -> bool:
    if admin_reauth_active():
        return True
    st.error("Sensitive action blocked. Re-authenticate with your current admin password first.")
    return False


st.set_page_config(page_title="User Management", layout="wide")
apply_admin_theme("User Management", "Create and manage staff accounts.")

if not st.session_state.get("logged_in", False):
    st.warning("Session expired. Please log in again.")
    if st.button("Go to Login", key="register_user_go_login"):
        st.switch_page("app.py")
    st.stop()

if st.session_state.get("role") != "Admin":
    st.error("Admin access only")
    st.stop()

ensure_activity_log()
ensure_staff_management_columns()

tab1, tab2 = st.tabs(["Create User", "Manage Users"])

with tab1:
    st.subheader("Create New Staff Account")
    with st.form("create_user_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            username = st.text_input("Username", placeholder="Enter username")
        with c2:
            role = st.selectbox("Role", ["Cashier", "Manager", "Admin"])
        password = st.text_input("Password", type="password", placeholder="Enter password")
        password_confirm = st.text_input("Confirm Password", type="password", placeholder="Re-enter password")
        submit = st.form_submit_button("Create User", type="primary", use_container_width=True)

    if submit:
        if not username or not password:
            st.error("Username and password are required.")
        elif len(username.strip()) < 3:
            st.error("Username must be at least 3 characters.")
        elif len(password) < 6:
            st.error("Password must be at least 6 characters.")
        elif password != password_confirm:
            st.error("Passwords do not match.")
        else:
            conn = get_db()
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    INSERT INTO staff (username, password_hash, role, is_active)
                    VALUES (?, ?, ?, 1)
                    """,
                    (username.strip(), hash_password(password), role),
                )
                user_id = int(cur.lastrowid)
                log_activity(cur, "USER_CREATED", user_id, f"Created {role} user '{username.strip()}'.")
                conn.commit()
                show_success_summary(
                    "User created successfully.",
                    [
                        ("Username", username.strip()),
                        ("Role", role),
                        ("Status", "Active"),
                        ("Created At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    ],
                )
            except sqlite3.IntegrityError:
                conn.rollback()
                st.error(f"Username '{username.strip()}' already exists.")
            except Exception as e:
                conn.rollback()
                st.error(f"Error creating user: {e}")
            finally:
                conn.close()

with tab2:
    st.subheader("Current Staff Members")

    reauth_col1, reauth_col2 = st.columns([2, 1])
    with reauth_col1:
        admin_current_pw = st.text_input(
            "Admin Re-Auth Password",
            type="password",
            key="admin_reauth_password",
            placeholder="Enter your current admin password",
            help="Required before role change, reset, disable/enable, or delete.",
        )
    with reauth_col2:
        st.write("")
        st.write("")
        if st.button("Re-Authenticate", key="admin_reauth_submit", use_container_width=True):
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "SELECT password_hash FROM staff WHERE username = ?",
                (str(st.session_state.get("username", "")),),
            )
            row = cur.fetchone()
            conn.close()
            if not row:
                st.error("Admin account not found.")
            elif not verify_password(admin_current_pw or "", str(row[0])):
                st.error("Invalid admin password.")
            else:
                st.session_state.admin_reauth_until = time.time() + (10 * 60)
                show_success_summary("Re-authentication successful.", [("Valid For", "10 minutes")])
                st.rerun()

    if admin_reauth_active():
        ttl = int(max(0, st.session_state.get("admin_reauth_until", 0) - time.time()))
        st.caption(f"Sensitive actions unlocked for {ttl // 60:02d}:{ttl % 60:02d}.")
    else:
        st.caption("Sensitive actions are locked until re-authentication.")

    conn = get_db()
    users = pd.read_sql(
        """
        SELECT
            id,
            username,
            role,
            COALESCE(is_active, 1) AS is_active,
            COALESCE(must_change_password, 0) AS must_change_password
        FROM staff
        ORDER BY CASE role WHEN 'Admin' THEN 1 WHEN 'Manager' THEN 2 ELSE 3 END, username
        """,
        conn,
    )
    conn.close()

    if users.empty:
        st.info("No users found.")
        st.stop()

    st.caption(f"Total users: {len(users)}")
    active_admin_count = int(users[(users["role"] == "Admin") & (users["is_active"] == 1)].shape[0])

    for role_name in ["Admin", "Manager", "Cashier"]:
        subset = users[users["role"] == role_name].copy()
        if subset.empty:
            continue

        st.markdown(f"### {role_name}s ({len(subset)})")
        for _, row in subset.iterrows():
            user_id = int(row["id"])
            username = str(row["username"])
            current_role = str(row["role"])
            is_active = int(row["is_active"]) == 1
            must_change_password = int(row.get("must_change_password", 0) or 0) == 1
            is_self = username == str(st.session_state.get("username", ""))

            if not is_active:
                status_label = "Disabled"
            elif must_change_password:
                status_label = "Active - Password Reset Pending"
            else:
                status_label = "Active"
            status_color = "#16a34a" if is_active else "#b91c1c"
            st.markdown(
                f"""
                <div style="border:1px solid #d0d5df;border-radius:12px;padding:10px 12px;margin:8px 0;background:#ffffff;">
                    <div style="display:flex;justify-content:space-between;gap:8px;align-items:center;">
                        <div><strong>{username}</strong> (ID: {user_id})</div>
                        <div style="font-weight:700;color:{status_color};">{status_label}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            c1, c2, c3 = st.columns([2.1, 2.1, 1.8])
            with c1:
                new_role = st.selectbox(
                    "Role",
                    ["Cashier", "Manager", "Admin"],
                    index=["Cashier", "Manager", "Admin"].index(current_role),
                    key=f"user_role_select_{user_id}",
                )
                if st.button("Save Role", key=f"user_role_save_{user_id}", use_container_width=True):
                    if not require_admin_reauth():
                        pass
                    elif is_self and new_role != "Admin":
                        st.error("You cannot demote your own admin account here.")
                    else:
                        conn = get_db()
                        cur = conn.cursor()
                        try:
                            cur.execute("UPDATE staff SET role = ? WHERE id = ?", (new_role, user_id))
                            log_activity(cur, "USER_ROLE_CHANGED", user_id, f"Changed role for '{username}' from {current_role} to {new_role}.")
                            conn.commit()
                            show_success_summary(
                                "Role updated.",
                                [("User", username), ("Old Role", current_role), ("New Role", new_role)],
                            )
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error updating role: {e}")
                        finally:
                            conn.close()

            with c2:
                new_password = st.text_input("Reset Password", type="password", key=f"user_pw_{user_id}", placeholder="New password")
                confirm_new_password = st.text_input("Confirm Password", type="password", key=f"user_pw_confirm_{user_id}", placeholder="Re-enter new password")
                if st.button("Set New Password", key=f"user_pw_save_{user_id}", use_container_width=True):
                    if not require_admin_reauth():
                        pass
                    elif len(new_password or "") < 6:
                        st.error("Password must be at least 6 characters.")
                    elif (new_password or "") != (confirm_new_password or ""):
                        st.error("Passwords do not match.")
                    else:
                        conn = get_db()
                        cur = conn.cursor()
                        try:
                            cur.execute(
                                """
                                UPDATE staff
                                SET password_hash = ?, must_change_password = 1, password_changed_at = NULL
                                WHERE id = ?
                                """,
                                (hash_password(new_password), user_id),
                            )
                            log_activity(
                                cur,
                                "USER_PASSWORD_RESET",
                                user_id,
                                f"Reset password for '{username}' and forced password change on next login.",
                            )
                            conn.commit()
                            show_success_summary(
                                "Password reset successfully.",
                                [("User", username), ("Next Login", "Password change required")],
                            )
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error resetting password: {e}")
                        finally:
                            conn.close()

            with c3:
                action = "Disable User" if is_active else "Enable User"
                if st.button(action, key=f"user_toggle_{user_id}", use_container_width=True):
                    if not require_admin_reauth():
                        pass
                    elif is_self and is_active:
                        st.error("You cannot disable your own account.")
                    elif current_role == "Admin" and is_active and active_admin_count <= 1:
                        st.error("Cannot disable the last active admin.")
                    else:
                        conn = get_db()
                        cur = conn.cursor()
                        try:
                            next_active = 0 if is_active else 1
                            cur.execute("UPDATE staff SET is_active = ? WHERE id = ?", (next_active, user_id))
                            log_activity(
                                cur,
                                "USER_STATUS_CHANGED",
                                user_id,
                                f"{'Disabled' if next_active == 0 else 'Enabled'} user '{username}'.",
                            )
                            conn.commit()
                            show_success_summary(
                                "User status updated.",
                                [("User", username), ("Status", "Disabled" if next_active == 0 else "Active")],
                            )
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error updating status: {e}")
                        finally:
                            conn.close()

                confirm_delete = st.text_input("Type DELETE", key=f"user_delete_confirm_{user_id}", placeholder="DELETE")
                if st.button("Delete User", key=f"user_delete_{user_id}", use_container_width=True):
                    if not require_admin_reauth():
                        pass
                    elif confirm_delete.strip().upper() != "DELETE":
                        st.error("Type DELETE to confirm.")
                    elif is_self:
                        st.error("You cannot delete your own account.")
                    elif current_role == "Admin" and active_admin_count <= 1:
                        st.error("Cannot delete the last active admin.")
                    else:
                        conn = get_db()
                        cur = conn.cursor()
                        try:
                            cur.execute("DELETE FROM staff WHERE id = ?", (user_id,))
                            log_activity(cur, "USER_DELETED", user_id, f"Deleted user '{username}'.")
                            conn.commit()
                            show_success_summary("User deleted.", [("User", username), ("Status", "Deleted")])
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error deleting user: {e}")
                        finally:
                            conn.close()

        st.markdown("---")
