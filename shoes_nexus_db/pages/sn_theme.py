import streamlit as st


def apply_sn_theme():
    st.markdown(
        """
        <style>
        :root {
            --sn-black: #0b0b0f;
            --sn-red: #c41224;
            --sn-red-dark: #9f0918;
            --sn-white: #ffffff;
            --sn-surface: #2b0b12;
            --sn-border: #e5e8ef;
            --sn-text: #141821;
            --sn-muted: #5d6573;
        }

        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(1200px circle at 12% -12%, rgba(196,18,36,0.18), transparent 45%),
                radial-gradient(900px circle at 100% 0%, rgba(159,9,24,0.12), transparent 40%),
                linear-gradient(135deg, #f7eef1 0%, #f6edf0 45%, #f3e7eb 100%) !important;
        }

        [data-testid="stSidebarNav"] {
            display: none !important;
        }

        .dashboard-header,
        .register-header,
        .setup-header,
        .return-header,
        .sn-page-header {
            background: linear-gradient(135deg, #111318 0%, #c41224 100%) !important;
            color: #ffffff !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            border-radius: 16px !important;
            box-shadow: 0 14px 34px rgba(11,11,15,0.18) !important;
            padding: 1.1rem 1.2rem !important;
            margin-bottom: 1rem !important;
        }

        .dashboard-title,
        .register-title,
        .setup-title,
        .return-title {
            color: #ffffff !important;
            font-weight: 800 !important;
        }

        .dashboard-subtitle,
        .register-subtitle,
        .setup-subtitle,
        .return-subtitle {
            color: #f1f4fa !important;
            opacity: 1 !important;
        }

        .section-header {
            background: #ffffff !important;
            border: 1px solid var(--sn-border) !important;
            border-left: 5px solid var(--sn-red) !important;
            border-radius: 12px !important;
            box-shadow: 0 10px 24px rgba(11,11,15,0.06) !important;
        }

        .section-header h3 {
            color: var(--sn-text) !important;
        }

        .user-card,
        .product-card,
        .request-card,
        .chart-container {
            background: #ffffff !important;
            border: 1px solid var(--sn-border) !important;
            border-left-color: var(--sn-red) !important;
            border-left-width: 4px !important;
            border-radius: 12px !important;
            color: var(--sn-text) !important;
            box-shadow: 0 10px 24px rgba(11,11,15,0.06) !important;
        }

        h1, h2, h3, h4, .stSubheader, .stSubheader * {
            color: var(--sn-text) !important;
        }

        .stMarkdown p, .stMarkdown li, .stCaption {
            color: var(--sn-muted) !important;
            opacity: 1 !important;
        }

        .stButton > button,
        .stFormSubmitButton > button {
            background: var(--sn-black) !important;
            color: #ffffff !important;
            border: 1px solid var(--sn-black) !important;
            border-radius: 12px !important;
            font-weight: 700 !important;
        }

        .stButton > button *,
        .stFormSubmitButton > button * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }

        [data-testid="baseButton-primary"],
        [data-testid="baseButton-secondary"],
        [data-testid="baseButton-primary"] *,
        [data-testid="baseButton-secondary"] * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            opacity: 1 !important;
        }

        [data-testid="baseButton-primary"]:disabled,
        [data-testid="baseButton-secondary"]:disabled,
        [data-testid="baseButton-primary"]:disabled *,
        [data-testid="baseButton-secondary"]:disabled * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            opacity: 0.7 !important;
        }

        .stButton > button:hover,
        .stFormSubmitButton > button:hover {
            background: var(--sn-red-dark) !important;
            border-color: var(--sn-red-dark) !important;
        }

        .stTextInput input, .stTextArea textarea,
        .stNumberInput input,
        .stSelectbox [data-baseweb="select"] > div,
        .stDateInput input {
            background: #ffffff !important;
            color: var(--sn-text) !important;
            -webkit-text-fill-color: var(--sn-text) !important;
            border: 1px solid #d7dce6 !important;
            border-radius: 12px !important;
            opacity: 1 !important;
        }

        .stTextInput input::placeholder,
        .stTextArea textarea::placeholder,
        .stNumberInput input::placeholder {
            color: #7a8291 !important;
            opacity: 1 !important;
        }

        .stRadio [role="radiogroup"] label p,
        [data-testid="stWidgetLabel"] label,
        [data-testid="stWidgetLabel"] p {
            color: var(--sn-text) !important;
            font-weight: 600 !important;
        }

        [data-testid="stAlert"] {
            border: 1px solid var(--sn-border) !important;
            border-radius: 12px !important;
            background: #ffffff !important;
        }

        [data-testid="stAlert"] * {
            color: var(--sn-text) !important;
            opacity: 1 !important;
        }

        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            border: 1px solid var(--sn-border) !important;
            border-radius: 12px !important;
            box-shadow: 0 10px 24px rgba(11,11,15,0.05) !important;
            overflow: hidden;
        }

        [data-testid="stDataFrame"] *,
        [data-testid="stTable"] * {
            color: var(--sn-text) !important;
            opacity: 1 !important;
        }

        @media (max-width: 900px) {
            [data-testid="stHorizontalBlock"] {
                flex-direction: column !important;
            }
            [data-testid="stHorizontalBlock"] > div {
                width: 100% !important;
            }
            .stButton > button,
            .stFormSubmitButton > button,
            .stDownloadButton > button {
                width: 100% !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sn_header(title: str, subtitle: str):
    st.markdown(
        f"""
        <div class="sn-page-header">
            <h2 style="margin:0; color:#fff; font-weight:800;">{title}</h2>
            <p style="margin:.35rem 0 0; color:#f1f4fa;">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
