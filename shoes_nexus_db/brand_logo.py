import os
from functools import lru_cache

import streamlit as st


_LOGO_CANDIDATES = [
    "assets/logo.png",
    "assets/logo-transparent.png",
    "assets/shoes_nexus_logo.png",
    "logo.png",
]


@lru_cache(maxsize=1)
def get_brand_logo_path() -> str | None:
    override = str(st.session_state.get("brand_logo_path", "")).strip()
    if override:
        if os.path.isabs(override) and os.path.exists(override):
            return override
        rel_override = os.path.abspath(override)
        if os.path.exists(rel_override):
            return rel_override

    for rel in _LOGO_CANDIDATES:
        path = os.path.abspath(rel)
        if os.path.exists(path):
            return path
    return None


def render_brand_logo(width: int = 72) -> bool:
    logo_path = get_brand_logo_path()
    if not logo_path:
        return False
    st.image(logo_path, width=width)
    return True
