import streamlit as st

st.set_page_config(page_title="POS Workspace", layout="wide")

if not st.session_state.get("logged_in", False):
    st.warning("Session expired. Please log in again.")
    if st.button("Go to Login", key="pos_workspace_go_login"):
        st.switch_page("app.py")
    st.stop()

st.info("POS Workspace is unified with the main POS. Redirecting...")
st.switch_page("app.py")
