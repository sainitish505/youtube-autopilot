"""
frontend/pages/5_Settings.py — User settings: API keys, YouTube OAuth, video preferences.

Sections:
  1. OpenAI API Key — add / remove
  2. YouTube Channel — connect via OAuth / disconnect
  3. Video Preferences — voice, max length, privacy, model
"""
import os
import streamlit as st
import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Settings | YouTube Autopilot", page_icon="⚙️", layout="centered")

if not st.session_state.get("access_token"):
    st.warning("Please sign in first.")
    st.stop()


def get_headers():
    return {"Authorization": f"Bearer {st.session_state.access_token}"}


def fetch_key_status():
    try:
        with httpx.Client(base_url=API_URL, timeout=10) as c:
            return c.get("/api/keys", headers=get_headers()).json()
    except Exception:
        return {}


def fetch_settings():
    try:
        with httpx.Client(base_url=API_URL, timeout=10) as c:
            return c.get("/api/settings", headers=get_headers()).json()
    except Exception:
        return {}


def save_openai_key(key: str):
    try:
        with httpx.Client(base_url=API_URL, timeout=15) as c:
            return c.post("/api/keys/openai", json={"openai_api_key": key}, headers=get_headers()).json()
    except Exception as e:
        return {"error": str(e)}


def delete_openai_key():
    try:
        with httpx.Client(base_url=API_URL, timeout=10) as c:
            return c.delete("/api/keys/openai", headers=get_headers()).json()
    except Exception as e:
        return {"error": str(e)}


def get_youtube_connect_url():
    try:
        with httpx.Client(base_url=API_URL, timeout=10) as c:
            return c.get("/api/youtube/connect", headers=get_headers()).json()
    except Exception:
        return {}


def disconnect_youtube():
    try:
        with httpx.Client(base_url=API_URL, timeout=10) as c:
            return c.delete("/api/youtube/disconnect", headers=get_headers()).json()
    except Exception as e:
        return {"error": str(e)}


def update_settings(data: dict):
    try:
        with httpx.Client(base_url=API_URL, timeout=10) as c:
            return c.put("/api/settings", json=data, headers=get_headers()).json()
    except Exception as e:
        return {"error": str(e)}


st.title("⚙️ Settings")

# Check if returning from YouTube OAuth
query_params = st.query_params
if query_params.get("youtube_connected"):
    st.success("✅ YouTube channel connected successfully!")
    st.query_params.clear()

keys = fetch_key_status()
prefs = fetch_settings()

# ── Section 1: OpenAI API Key ─────────────────────────────────────────────────
st.markdown("## 🔑 OpenAI API Key")
st.markdown(
    "Your OpenAI API key is used to generate video scripts, voiceovers (TTS), "
    "images (DALL-E), and video clips (Sora). It is **encrypted at rest** and "
    "never returned in plain text."
)

has_key = keys.get("has_openai_key", False)
if has_key:
    added_at = keys.get("openai_added_at", "")
    st.success(f"✅ OpenAI key connected" + (f" · Added {str(added_at)[:10]}" if added_at else ""))
    col1, col2 = st.columns(2)
    with col1:
        with st.form("update_key_form"):
            new_key = st.text_input(
                "Update API Key",
                type="password",
                placeholder="sk-...",
                help="Enter your new OpenAI API key to replace the existing one"
            )
            if st.form_submit_button("Update Key", use_container_width=True):
                if new_key.startswith("sk-"):
                    res = save_openai_key(new_key)
                    if "error" in res:
                        st.error(f"Failed: {res['error']}")
                    else:
                        st.success("Key updated!")
                        st.rerun()
                else:
                    st.error("Key must start with 'sk-'")
    with col2:
        st.markdown("")
        st.markdown("")
        if st.button("🗑 Remove Key", use_container_width=True):
            res = delete_openai_key()
            if "error" not in res:
                st.success("Key removed.")
                st.rerun()
else:
    st.warning("⚠️ No OpenAI key configured. You need this to generate videos.")
    with st.form("add_key_form"):
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            placeholder="sk-proj-...",
            help="Get your key at platform.openai.com/api-keys"
        )
        st.markdown("[Get your API key →](https://platform.openai.com/api-keys)", unsafe_allow_html=False)
        if st.form_submit_button("Save Key", use_container_width=True, type="primary"):
            if not api_key:
                st.error("Please enter your API key")
            elif not api_key.startswith("sk-"):
                st.error("Invalid key format — must start with 'sk-'")
            else:
                res = save_openai_key(api_key)
                if "error" in res:
                    st.error(f"Failed to save key: {res['error']}")
                else:
                    st.success("✅ OpenAI key saved!")
                    st.rerun()

st.markdown("---")

# ── Section 2: YouTube Channel ────────────────────────────────────────────────
st.markdown("## 📺 YouTube Channel")
st.markdown(
    "Connect your YouTube channel so the agent can upload videos automatically. "
    "We store your OAuth refresh token encrypted — we never store your Google password."
)

has_yt = keys.get("has_youtube_token", False)
channel_name = keys.get("youtube_channel_name", "")
channel_id = keys.get("youtube_channel_id", "")
yt_connected_at = keys.get("youtube_connected_at", "")

if has_yt:
    st.success(
        f"✅ Connected to **{channel_name or 'Unknown Channel'}**"
        + (f" (`{channel_id}`)" if channel_id else "")
        + (f" · Connected {str(yt_connected_at)[:10]}" if yt_connected_at else "")
    )
    col1, col2 = st.columns(2)
    with col1:
        yt_data_reconnect = get_youtube_connect_url()
        reconnect_url = yt_data_reconnect.get("auth_url", "")
        if reconnect_url:
            st.link_button("🔄 Reconnect YouTube", reconnect_url, use_container_width=True)
        else:
            st.warning("YOUTUBE_CLIENT_ID not configured on the server.")
    with col2:
        if st.button("🔌 Disconnect YouTube", use_container_width=True):
            res = disconnect_youtube()
            if "error" not in res:
                st.success("YouTube disconnected.")
                st.rerun()
else:
    st.info("No YouTube channel connected. Videos will be generated but not uploaded.")
    yt_data_connect = get_youtube_connect_url()
    connect_url = yt_data_connect.get("auth_url", "")
    if connect_url:
        st.link_button(
            "🔗 Connect YouTube Channel",
            connect_url,
            use_container_width=True,
            type="primary",
        )
    else:
        st.warning(
            "YouTube OAuth is not configured on the server. "
            "Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in your .env file."
        )

st.markdown("---")

# ── Section 3: Video Preferences ─────────────────────────────────────────────
st.markdown("## 🎬 Video Preferences")
st.markdown("These settings apply to all new video jobs you create.")

with st.form("prefs_form"):
    col1, col2 = st.columns(2)

    with col1:
        default_niche = st.text_input(
            "Default Niche",
            value=prefs.get("default_niche", ""),
            placeholder="e.g. personal finance, fitness, travel",
            help="Leave blank to let the AI pick the trending topic automatically"
        )
        max_minutes = st.slider(
            "Max Video Length (minutes)",
            min_value=3, max_value=20,
            value=prefs.get("max_video_minutes", 10),
            help="Maximum video duration — more minutes = higher cost"
        )
        upload_privacy = st.selectbox(
            "Upload Privacy",
            options=["public", "unlisted", "private"],
            index=["public", "unlisted", "private"].index(prefs.get("upload_privacy", "public")),
            help="YouTube privacy setting for uploaded videos"
        )

    with col2:
        tts_voice = st.selectbox(
            "TTS Voice",
            options=["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
            index=["alloy", "echo", "fable", "onyx", "nova", "shimmer"].index(
                prefs.get("tts_voice", "alloy")
            ),
            help="OpenAI TTS voice for voiceovers"
        )
        video_model = st.selectbox(
            "Video Model",
            options=["sora-2"],
            index=0,
            help="AI model used for video clip generation"
        )
        auto_approve = st.number_input(
            "Auto-Approve Under ($)",
            min_value=0.0, max_value=50.0,
            value=float(prefs.get("auto_approve_under_dollars", 2.0)),
            step=0.5,
            help="Automatically approve plans with estimated cost below this threshold"
        )

    autonomous = st.toggle(
        "Autonomous Mode",
        value=prefs.get("autonomous_mode", True),
        help="Skip human approval step for plans under the auto-approve threshold"
    )

    if st.form_submit_button("💾 Save Preferences", use_container_width=True, type="primary"):
        payload = {
            "default_niche": default_niche,
            "max_video_minutes": max_minutes,
            "upload_privacy": upload_privacy,
            "tts_voice": tts_voice,
            "video_model": video_model,
            "auto_approve_under_dollars": auto_approve,
            "autonomous_mode": autonomous,
        }
        res = update_settings(payload)
        if "error" in res:
            st.error(f"Failed to save: {res['error']}")
        else:
            st.success("✅ Preferences saved!")

st.markdown("---")

# ── Section 4: Account ────────────────────────────────────────────────────────
st.markdown("## 👤 Account")
st.markdown(f"**Email:** {st.session_state.get('user_email', '—')}")
st.markdown(f"**User ID:** `{st.session_state.get('user_id', '—')}`")

if st.button("Sign Out", use_container_width=False):
    for key in ["access_token", "user_id", "user_email"]:
        st.session_state[key] = None
    st.rerun()
