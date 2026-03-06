import streamlit as st
from datetime import datetime, timezone, timedelta
import time
import base64
from brand_logo import get_brand_logo_path


SESSION_TIMEOUT = 60 * 30


def now_nairobi_str() -> str:
    return datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S EAT")


def enforce_admin_page_session(login_button_key: str = "admin_theme_go_login") -> None:
    logged_in = bool(st.session_state.get("logged_in", False))
    if not logged_in:
        st.warning("Session expired. Please log in again.")
        if st.button("Go to Login", key=login_button_key):
            st.switch_page("app.py")
        st.stop()

    last_activity = st.session_state.get("last_activity")
    now_ts = time.time()
    if isinstance(last_activity, (int, float)) and (now_ts - last_activity > SESSION_TIMEOUT):
        st.session_state.clear()
        st.session_state["session_expired_notice"] = True
        st.warning("Session expired. Please log in again.")
        if st.button("Go to Login", key=login_button_key):
            st.switch_page("app.py")
        st.stop()

    st.session_state["last_activity"] = now_ts


def render_page_actions() -> None:
    enforce_admin_page_session("admin_theme_go_login_actions")
    col_back, col_logout = st.columns([1, 1])
    with col_back:
        if st.button("Back to Main", key="admin_theme_back_main", use_container_width=True):
            st.switch_page("app.py")
    with col_logout:
        if st.button("Logout", key="admin_theme_logout", use_container_width=True):
            st.session_state.clear()
            st.switch_page("app.py")


def apply_admin_theme(title: str, subtitle: str = "") -> None:
    enforce_admin_page_session("admin_theme_go_login_header")
    st.markdown(
        """
        <style>
        :root {
            --sn-bg: #2b0b12;
            --sn-surface: #ffffff;
            --sn-text: #111111;
            --sn-muted: #4b5563;
            --sn-red: #c41224;
            --sn-black: #0b0b0f;
            --sn-border: #d0d5df;
        }

        .stApp {
            background:
                radial-gradient(1200px circle at 12% -12%, rgba(196,18,36,0.18), transparent 45%),
                radial-gradient(900px circle at 100% 0%, rgba(159,9,24,0.12), transparent 40%),
                linear-gradient(135deg, #f7eef1 0%, #f6edf0 45%, #f3e7eb 100%) !important;
            color: var(--sn-text) !important;
        }
        h1, h2, h3, h4, h5, h6, p, label, span, div { color: var(--sn-text); }

        .dashboard-header, .register-header, .setup-header, .return-header {
            background: linear-gradient(135deg, #0b0b0f 0%, #c41224 100%) !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            color: #ffffff !important;
            box-shadow: 0 8px 20px rgba(11, 11, 15, 0.18) !important;
        }

        .dashboard-header *, .register-header *, .setup-header *, .return-header * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }

        .section-header {
            background: #ffffff !important;
            border: 1px solid var(--sn-border) !important;
            border-left: 4px solid var(--sn-red) !important;
            color: var(--sn-text) !important;
        }

        .stMetric {
            background: #ffffff !important;
            border: 1px solid var(--sn-border) !important;
            border-radius: 12px !important;
            padding: 10px 12px !important;
        }
        [data-testid="stMetricLabel"], [data-testid="stMetricValue"] { color: var(--sn-text) !important; }

        [data-baseweb="input"], [data-baseweb="select"], [data-baseweb="textarea"] {
            background: #ffffff !important;
            border: 1px solid var(--sn-border) !important;
            border-radius: 10px !important;
        }
        input, textarea, [data-baseweb="select"] * { color: var(--sn-text) !important; }
        input::placeholder, textarea::placeholder { color: #6b7280 !important; opacity: 1 !important; }

        .stTextInput > div > div > input,
        .stNumberInput > div > div > input,
        .stTextArea textarea,
        .stDateInput > div > div > input,
        .stSelectbox [data-baseweb="select"] > div,
        .stMultiSelect [data-baseweb="select"] > div {
            background: #ffffff !important;
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
            border: 1px solid var(--sn-border) !important;
            opacity: 1 !important;
        }

        .stSelectbox [data-baseweb="select"] *,
        .stMultiSelect [data-baseweb="select"] *,
        [data-baseweb="popover"] [role="listbox"] *,
        [data-baseweb="popover"] [role="option"] * {
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
            opacity: 1 !important;
        }

        [data-baseweb="popover"] [role="listbox"],
        [data-baseweb="popover"] [role="option"] {
            background: #ffffff !important;
        }

        .stNumberInput [data-baseweb="input"] {
            background: #ffffff !important;
            border: 1px solid var(--sn-border) !important;
        }
        .stNumberInput [data-baseweb="input"] input,
        .stNumberInput [data-baseweb="input"] button,
        .stNumberInput [data-baseweb="input"] [role="button"] {
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
            background: #ffffff !important;
            opacity: 1 !important;
        }

        [data-baseweb="calendar"],
        [data-baseweb="calendar"] * {
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
            opacity: 1 !important;
        }

        [data-baseweb="calendar"] {
            background: #ffffff !important;
            border: 1px solid var(--sn-border) !important;
            border-radius: 12px !important;
        }

        [data-baseweb="calendar"] [aria-selected="true"],
        [data-baseweb="calendar"] [aria-selected="true"] * {
            background: #e11d2a !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }

        .stSelectbox label, .stNumberInput label, .stTextInput label, .stTextArea label, .stRadio label, .stDateInput label {
            color: var(--sn-text) !important;
            font-weight: 600 !important;
        }

        .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
            background: var(--sn-black) !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            border: 1px solid #1f2430 !important;
            border-radius: 10px !important;
            font-weight: 700 !important;
        }
        .stButton > button *, .stFormSubmitButton > button *, .stDownloadButton > button * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            opacity: 1 !important;
        }
        [data-testid="baseButton-primary"], [data-testid="baseButton-secondary"],
        [data-testid="baseButton-primary"] *, [data-testid="baseButton-secondary"] * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            opacity: 1 !important;
        }
        .stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover {
            border-color: var(--sn-red) !important;
            box-shadow: 0 0 0 1px var(--sn-red) inset !important;
        }

        .stCaption, .stCaption *,
        [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {
            color: #374151 !important;
            opacity: 1 !important;
        }

        /* Keep section/expander headings readable in all states */
        [data-testid="stExpander"] summary {
            background: #ffffff !important;
            border: 1px solid var(--sn-border) !important;
            border-radius: 10px !important;
        }
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary *,
        [data-testid="stExpander"] [data-testid="stMarkdownContainer"] h1,
        [data-testid="stExpander"] [data-testid="stMarkdownContainer"] h2,
        [data-testid="stExpander"] [data-testid="stMarkdownContainer"] h3,
        [data-testid="stExpander"] [data-testid="stMarkdownContainer"] h4,
        [data-testid="stExpander"] [data-testid="stMarkdownContainer"] h5,
        [data-testid="stExpander"] [data-testid="stMarkdownContainer"] h6 {
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
            opacity: 1 !important;
        }

        .stAlert {
            border-radius: 10px !important;
            border: 1px solid #f1d0d4 !important;
            border-left: 4px solid #c41224 !important;
            background: #fff7f8 !important;
        }
        [data-testid="stAlert"],
        [data-testid="stAlert"] * {
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
            opacity: 1 !important;
        }

        .sn-admin-hero-card {
            background:#ffffff;
            border:1px solid #d0d5df;
            border-radius:16px;
            padding:10px 14px;
            margin:0 0 8px 0;
        }

        .sn-admin-hero-head {
            display:flex;
            align-items:center;
            justify-content:center;
            gap:0.35rem;
        }

        .sn-admin-hero-head h2 {
            margin:0;
            color:#111111;
            font-size:1.45rem;
        }

        .sn-admin-hero-logo img {
            width:64px;
            height:auto;
            object-fit:contain;
        }

        @media (max-width: 900px) {
            [data-testid="stHorizontalBlock"] {
                flex-direction: column !important;
            }
            [data-testid="stHorizontalBlock"] > div {
                width: 100% !important;
            }
            .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
                width: 100% !important;
            }
            .sn-admin-hero-logo img {
                width:52px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    logo_markup = ""
    try:
        logo_path = get_brand_logo_path()
        if logo_path:
            with open(logo_path, "rb") as f:
                logo_b64 = base64.b64encode(f.read()).decode("ascii")
            logo_markup = (
                "<div class='sn-admin-hero-logo'>"
                f"<img src='data:image/png;base64,{logo_b64}' alt='Shoes Nexus Logo'/>"
                "</div>"
            )
    except Exception:
        logo_markup = ""

    subtitle_html = (
        f"<p style='margin:4px 0 0 0;color:#4b5563;font-size:0.96rem;text-align:center;'>{subtitle}</p>"
        if subtitle
        else ""
    )
    st.markdown(
        f"""
        <div class='sn-admin-hero-card'>
            <div class='sn-admin-hero-head'>
                <h2>{title}</h2>
                {logo_markup}
            </div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_page_actions()
