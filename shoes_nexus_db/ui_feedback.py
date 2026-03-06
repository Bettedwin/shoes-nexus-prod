import html
from typing import Iterable, Tuple

import streamlit as st


def show_success_summary(title: str, rows: Iterable[Tuple[str, str]] | None = None) -> None:
    st.success(title)
    if not rows:
        return
    lines = []
    for label, value in rows:
        lines.append(
            f"<div><strong>{html.escape(str(label))}:</strong> {html.escape(str(value))}</div>"
        )
    st.markdown(
        (
            "<div style='background:#ffffff;border:1px solid #e5e8ef;border-left:4px solid #c41224;"
            "border-radius:10px;padding:10px 12px;margin:6px 0 10px 0;color:#141821;'>"
            + "".join(lines)
            + "</div>"
        ),
        unsafe_allow_html=True,
    )

