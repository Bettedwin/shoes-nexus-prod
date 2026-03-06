from db_config import DB_PATH
import sqlite3
import pandas as pd
import streamlit as st
from theme_admin import apply_admin_theme


st.set_page_config(page_title="Activity Log", layout="wide")
apply_admin_theme("Activity Log", "Review and filter system activity events.")


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


ensure_activity_log()

conn = get_db()
df = pd.read_sql(
    """
    SELECT id, event_type, reference_id, role, username, message, created_at
    FROM activity_log
    ORDER BY id DESC
    """,
    conn,
)
conn.close()

if df.empty:
    st.info("No activity recorded yet.")
    st.stop()

df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", format="mixed")

col1, col2, col3 = st.columns(3)
with col1:
    start_date = st.date_input("From", value=df["created_at"].min().date())
with col2:
    end_date = st.date_input("To", value=df["created_at"].max().date())
with col3:
    event_options = ["All"] + sorted(df["event_type"].dropna().unique().tolist())
    selected_event = st.selectbox("Event Type", event_options)

mask = (df["created_at"].dt.date >= start_date) & (df["created_at"].dt.date <= end_date)
if selected_event != "All":
    mask &= df["event_type"] == selected_event

filtered = df.loc[mask].copy()

if filtered.empty:
    st.warning("No records match your filters.")
else:
    st.dataframe(filtered, use_container_width=True, hide_index=True)
