"""
frontend/components/api_key_form.py — Encrypted API key input component.

Usage:
    from frontend.components.api_key_form import render_openai_key_section
    render_openai_key_section(key_status, on_save_fn, on_delete_fn)
"""
import streamlit as st
from typing import Callable, Dict, Any


def render_openai_key_section(
    key_status: Dict[str, Any],
    on_save: Callable[[str], Dict],
    on_delete: Callable[[], Dict],
):
    """
    Render the OpenAI API key add/update/delete section.

    Parameters
    ----------
    key_status : dict from /api/keys endpoint
    on_save : callable that takes a key string, returns response dict
    on_delete : callable that takes no args, returns response dict
    """
    has_key = key_status.get("has_openai_key", False)

    if has_key:
        added_at = str(key_status.get("openai_added_at", ""))[:10]
        st.success(f"✅ OpenAI key saved" + (f" (added {added_at})" if added_at else ""))

        col1, col2 = st.columns([3, 1])
        with col1:
            with st.form("update_openai_key"):
                new_key = st.text_input("Update Key", type="password", placeholder="sk-...")
                if st.form_submit_button("Update"):
                    _handle_save(new_key, on_save)
        with col2:
            st.markdown("")
            st.markdown("")
            if st.button("Remove", key="del_openai_key"):
                res = on_delete()
                if "error" not in res:
                    st.success("Key removed.")
                    st.rerun()
    else:
        st.warning("No OpenAI key added yet.")
        with st.form("add_openai_key"):
            api_key = st.text_input(
                "OpenAI API Key",
                type="password",
                placeholder="sk-proj-...",
                help="Required to generate scripts, voiceovers, images, and video clips.",
            )
            if st.form_submit_button("Save Key", type="primary"):
                _handle_save(api_key, on_save)


def _handle_save(key: str, on_save: Callable):
    if not key:
        st.error("Please enter a key.")
        return
    if not key.startswith("sk-"):
        st.error("Invalid key — must start with 'sk-'")
        return
    res = on_save(key)
    if "error" in res:
        st.error(f"Failed: {res['error']}")
    else:
        st.success("Key saved!")
        st.rerun()
