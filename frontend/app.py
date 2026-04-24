"""
frontend/app.py — Multi-tenant Streamlit frontend with Supabase auth.

Run: streamlit run frontend/app.py
"""
import os
import streamlit as st
import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8000")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

st.set_page_config(
    page_title="YouTube Autopilot",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: 700; color: #ff4b4b; }
    .status-card { background: #1e1e2e; border-radius: 12px; padding: 16px; margin: 8px 0; }
    .agent-done { color: #a6e3a1; }
    .agent-running { color: #f9e2af; }
    .agent-failed { color: #f38ba8; }
    .agent-pending { color: #6c7086; }
    .metric-card { background: #313244; border-radius: 8px; padding: 12px; text-align: center; }
</style>
""", unsafe_allow_html=True)


def init_session():
    """Initialize session state defaults."""
    for key, default in [
        ("access_token", None),
        ("user_id", None),
        ("user_email", None),
        ("auth_mode", "signin"),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default


def show_auth_page():
    """Login / Sign Up page."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="main-header">🎬 YouTube Autopilot</div>', unsafe_allow_html=True)
        st.markdown("##### AI-Powered YouTube Channel on Autopilot")
        st.markdown("---")

        tab_in, tab_up = st.tabs(["Sign In", "Sign Up"])

        with tab_in:
            with st.form("signin_form"):
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign In", use_container_width=True)

            if submitted:
                res = _api_post("/api/auth/signin", {"email": email, "password": password})
                if res and "access_token" in res:
                    st.session_state.access_token = res["access_token"]
                    st.session_state.user_id = res["user_id"]
                    st.session_state.user_email = res["email"]
                    st.rerun()
                else:
                    st.error("Invalid email or password")

        with tab_up:
            with st.form("signup_form"):
                name = st.text_input("Display Name")
                email2 = st.text_input("Email", placeholder="you@example.com", key="signup_email")
                pass2 = st.text_input("Password", type="password", key="signup_pass")
                submitted2 = st.form_submit_button("Create Account", use_container_width=True)

            if submitted2:
                res = _api_post("/api/auth/signup", {"email": email2, "password": pass2, "display_name": name})
                if res and "access_token" in res:
                    st.success("Account created! Please check your email to verify, then sign in.")
                else:
                    st.error(f"Signup failed: {res}")


def show_sidebar():
    """Authenticated sidebar with user info and nav."""
    with st.sidebar:
        st.markdown("### 🎬 YouTube Autopilot")
        st.markdown(f"**{st.session_state.user_email}**")
        st.markdown("---")
        st.page_link("pages/1_Dashboard.py", label="📊 Dashboard", icon="📊")
        st.page_link("pages/2_New_Video.py", label="➕ New Video", icon="➕")
        st.page_link("pages/3_My_Videos.py", label="🎥 My Videos", icon="🎥")
        st.page_link("pages/4_Analytics.py", label="📈 Analytics", icon="📈")
        st.page_link("pages/5_Settings.py", label="⚙️ Settings", icon="⚙️")
        st.markdown("---")
        if st.button("Sign Out", use_container_width=True):
            for key in ["access_token", "user_id", "user_email"]:
                st.session_state[key] = None
            st.rerun()


def _api_post(path: str, data: dict) -> dict:
    try:
        with httpx.Client(base_url=API_URL, timeout=15) as client:
            headers = {}
            if st.session_state.get("access_token"):
                headers["Authorization"] = f"Bearer {st.session_state.access_token}"
            res = client.post(path, json=data, headers=headers)
            return res.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return {}


def _api_get(path: str) -> dict:
    try:
        with httpx.Client(base_url=API_URL, timeout=15) as client:
            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
            res = client.get(path, headers=headers)
            return res.json()
    except Exception as e:
        return {}


# ── Main App ──────────────────────────────────────────────────────────────────
init_session()

if not st.session_state.access_token:
    show_auth_page()
else:
    show_sidebar()
    st.markdown('<div class="main-header">Welcome to YouTube Autopilot 🎬</div>', unsafe_allow_html=True)
    st.markdown("Use the sidebar to navigate. Click **New Video** to generate your first video!")

    col1, col2, col3, col4 = st.columns(4)
    stats = _api_get("/api/analytics/summary")
    with col1:
        st.metric("Total Videos", stats.get("total_videos", 0))
    with col2:
        st.metric("Total Cost", f"${stats.get('total_cost_usd', 0.0):.2f}")
    with col3:
        st.metric("Success Rate", f"{stats.get('success_rate', 0.0):.1f}%")
    with col4:
        st.metric("This Month", stats.get("videos_this_month", 0))
