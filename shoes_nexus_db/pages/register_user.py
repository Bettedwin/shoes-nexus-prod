from db_config import DB_PATH
import streamlit as st
import sqlite3
from security import hash_password
from datetime import datetime

# ============================================
# DATABASE CONNECTION
# ============================================
def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# ============================================
# PAGE SETUP
# ============================================
st.set_page_config(page_title="Register User", layout="centered")

# ============================================
# ACCESS CONTROL - Admin Only
# ============================================
if st.session_state.get("role") != "Admin":
    st.error("⛔ Admin access only")
    st.stop()

# ============================================
# CUSTOM CSS
# ============================================
st.markdown("""
    <style>
    .register-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        color: white;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    
    .register-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    .register-subtitle {
        font-size: 1.1rem;
        opacity: 0.9;
    }
    
    .user-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border-left: 4px solid #667eea;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================
# HEADER
# ============================================
st.markdown(f"""
    <div class="register-header">
        <div class="register-title">👤 User Management</div>
        <div class="register-subtitle">Create and manage staff accounts</div>
    </div>
""", unsafe_allow_html=True)

# ============================================
# TABS: Create User | View Users
# ============================================
tab1, tab2 = st.tabs(["➕ Create New User", "👥 View All Users"])

# ============================================
# TAB 1: CREATE NEW USER
# ============================================
with tab1:
    st.subheader("Create New Staff Account")
    
    with st.form("create_user_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            username = st.text_input(
                "Username *",
                placeholder="Enter username",
                help="Unique username for login"
            )
        
        with col2:
            role = st.selectbox(
                "Role *",
                ["Cashier", "Manager", "Admin"],
                help="User access level"
            )
        
        password = st.text_input(
            "Password *",
            type="password",
            placeholder="Enter password",
            help="Minimum 6 characters recommended"
        )
        
        password_confirm = st.text_input(
            "Confirm Password *",
            type="password",
            placeholder="Re-enter password"
        )
        
        full_name = st.text_input(
            "Full Name (optional)",
            placeholder="Employee's full name"
        )
        
        notes = st.text_area(
            "Notes (optional)",
            placeholder="Any additional information about this user"
        )
        
        submit = st.form_submit_button("➕ Create User", type="primary", use_container_width=True)
        
        if submit:
            # Validation
            if not username or not password:
                st.error("⚠️ Username and password are required")
            elif len(username) < 3:
                st.error("⚠️ Username must be at least 3 characters")
            elif len(password) < 6:
                st.error("⚠️ Password must be at least 6 characters")
            elif password != password_confirm:
                st.error("⚠️ Passwords do not match")
            else:
                conn = get_db()
                cur = conn.cursor()
                
                try:
                    # Hash the password
                    hashed_password = hash_password(password)
                    
                    # Insert new user
                    cur.execute("""
                        INSERT INTO staff (username, password_hash, role)
                        VALUES (?, ?, ?)
                    """, (username, hashed_password, role))
                    
                    user_id = cur.lastrowid
                    
                    # Activity log
                    cur.execute("""
                        INSERT INTO activity_log
                        (event_type, reference_id, role, username, message)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        "USER_CREATED",
                        user_id,
                        st.session_state.role,
                        st.session_state.username,
                        f"Created new {role} user: {username}"
                    ))
                    
                    conn.commit()
                    
                    st.success(f"✅ User '{username}' created successfully!")
                    st.balloons()
                    
                    st.info(f"""
                    **Account Details:**
                    - Username: {username}
                    - Role: {role}
                    - Created by: {st.session_state.username}
                    - Created at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                    """)
                    
                except sqlite3.IntegrityError:
                    st.error(f"❌ Username '{username}' already exists. Please choose a different username.")
                except Exception as e:
                    conn.rollback()
                    st.error(f"❌ Error creating user: {e}")
                finally:
                    conn.close()

# ============================================
# TAB 2: VIEW ALL USERS
# ============================================
with tab2:
    st.subheader("Current Staff Members")
    
    conn = get_db()
    
    # Get all users
    cur = conn.cursor()
    cur.execute("""
        SELECT id, username, role
        FROM staff
        ORDER BY role, username
    """)
    
    users = cur.fetchall()
    conn.close()
    
    if not users:
        st.info("No users found")
    else:
        # Group by role
        roles = {}
        for user_id, username, role in users:
            if role not in roles:
                roles[role] = []
            roles[role].append((user_id, username))
        
        # Display by role
        for role in ["Admin", "Manager", "Cashier"]:
            if role in roles:
                st.markdown(f"### {role}s ({len(roles[role])})")
                
                for user_id, username in roles[role]:
                    col1, col2, col3 = st.columns([3, 2, 2])
                    
                    with col1:
                        st.markdown(f"""
                        <div class="user-card">
                            <strong>👤 {username}</strong><br>
                            <small>ID: {user_id}</small>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        # Prevent deleting current user
                        if username == st.session_state.username:
                            st.info("(Current User)")
                    
                    with col3:
                        # Delete button (optional - be careful!)
                        if st.button(f"🗑️ Delete", key=f"del_{user_id}"):
                            if username == st.session_state.username:
                                st.error("❌ Cannot delete your own account")
                            else:
                                # Show confirmation
                                st.warning(f"⚠️ Delete user '{username}'? This action cannot be undone.")
                
                st.markdown("---")
        
        st.info(f"**Total Users:** {len(users)}")

# ============================================
# FOOTER
# ============================================
st.markdown("---")
st.markdown(
    '<p style="text-align: center; color: #95a5a6; font-size: 0.85rem;">User Management System - Admin Only</p>',
    unsafe_allow_html=True
)