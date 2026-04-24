"""
frontend/components/auth.py — Reusable Supabase auth components.

Usage:
    from frontend.components.auth import require_auth, show_user_badge
    require_auth()  # stops page if not signed in
"""
import os
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")


def require_auth():
    """Stop page rendering if user is not authenticated."""
    if not st.session_state.get("access_token"):
        st.warning("🔒 Please sign in to continue.")
        st.page_link("app.py", label="Go to Sign In", icon="🔑")
        st.stop()


def show_user_badge():
    """Show a small user badge in the sidebar."""
    email = st.session_state.get("user_email", "")
    if email:
        st.sidebar.markdown(f"👤 **{email}**")


def clear_session():
    """Clear all auth-related session state."""
    for key in ["access_token", "user_id", "user_email"]:
        st.session_state[key] = None


def get_auth_headers() -> dict:
    """Return Authorization header dict for API calls."""
    token = st.session_state.get("access_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}
