from db_config import DB_PATH
import streamlit as st
import sqlite3
from security import verify_password
from ui_feedback import show_success_summary

# ============================================
# PAGE CONFIG - MUST BE FIRST
# ============================================
st.set_page_config(
    page_title="Shoes Nexus - Login",
    page_icon="👟",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ============================================
# CUSTOM CSS FOR MODERN LOGIN
# ============================================
st.markdown("""
    <style>
    /* Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Center the login container */
    .stApp {
        background:
            radial-gradient(900px circle at 8% -10%, rgba(196,18,36,0.12), transparent 45%),
            #f6f7fb;
    }
    
    /* Login card styling */
    .login-container {
        background: white;
        padding: 3rem 2.5rem;
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        max-width: 450px;
        margin: 5rem auto;
    }
    
    /* Title styling */
    .login-title {
        text-align: center;
        color: #0b0b0f;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    .login-subtitle {
        text-align: center;
        color: #5d6573;
        font-size: 1rem;
        margin-bottom: 2rem;
    }
    
    /* Input field styling */
    .stTextInput > div > div > input {
        border-radius: 10px;
        border: 2px solid #e0e0e0;
        padding: 12px 15px;
        font-size: 1rem;
        transition: all 0.3s ease;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #c41224;
        box-shadow: 0 0 0 3px rgba(196, 18, 36, 0.14);
    }
    
    /* Button styling */
    .stButton > button {
        width: 100%;
        background: #0b0b0f;
        color: white;
        border: none;
        border-radius: 10px;
        padding: 15px;
        font-size: 1.1rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
        margin-top: 1rem;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        background: #9f0918;
        box-shadow: 0 10px 25px rgba(196, 18, 36, 0.3);
    }
    
    /* Icon styling */
    .login-icon {
        text-align: center;
        font-size: 4rem;
        margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================
# LOGIN CONTAINER
# ============================================
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.markdown('<div class="login-icon">👟</div>', unsafe_allow_html=True)
    st.markdown('<h1 class="login-title">Shoes Nexus</h1>', unsafe_allow_html=True)
    st.markdown('<p class="login-subtitle">Retail Management System</p>', unsafe_allow_html=True)
    
    # Login form
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input(
            "Username",
            placeholder="Enter your username",
            label_visibility="visible"
        )
        
        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter your password",
            label_visibility="visible"
        )
        
        submit = st.form_submit_button("Sign In")
        
        if submit:
            if not username or not password:
                st.error("⚠️ Please enter both username and password")
            else:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()

                # Fetch hashed password + role
                cursor.execute(
                    "SELECT password_hash, role FROM staff WHERE username=?",
                    (username,)
                )
                user = cursor.fetchone()
                conn.close()

                if user:
                    stored_hash, role = user

                    # Verify password
                    if verify_password(password, stored_hash):
                        st.session_state.username = username
                        st.session_state.role = role
                        st.session_state.logged_in = True
                        
                        show_success_summary(
                            f"Welcome back, {username}.",
                            [
                                ("User", username),
                                ("Role", role),
                            ],
                        )
                                                
                        # Redirect based on role
                        if role == "Admin":
                            st.info("🔄 Redirecting to Admin Dashboard...")
                        elif role == "Manager":
                            st.info("🔄 Redirecting to Manager Dashboard...")
                        else:
                            st.info("🔄 Redirecting to POS System...")
                        
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password")
                else:
                    st.error("❌ Invalid username or password")
    
    # Footer
    st.markdown("---")
    st.markdown(
        '<p style="text-align: center; color: #95a5a6; font-size: 0.85rem;">© 2026 Shoes Nexus. All rights reserved.</p>',
        unsafe_allow_html=True
    )
