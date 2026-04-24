"""
frontend/pages/2_New_Video.py — Create a new video generation job.
"""
import os
import streamlit as st
import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="New Video | YouTube Autopilot", page_icon="➕", layout="centered")

if not st.session_state.get("access_token"):
    st.warning("Please sign in first.")
    st.stop()


def get_headers():
    return {"Authorization": f"Bearer {st.session_state.access_token}"}


def check_keys():
    try:
        with httpx.Client(base_url=API_URL, timeout=10) as c:
            return c.get("/api/keys", headers=get_headers()).json()
    except Exception:
        return {}


st.title("➕ Generate New Video")

keys = check_keys()
if not keys.get("has_openai_key"):
    st.warning("⚠️ You haven't added your OpenAI API key yet. Go to **Settings** first.")
    if st.button("Go to Settings"):
        st.switch_page("pages/5_Settings.py")
    st.stop()

if not keys.get("has_youtube_token"):
    st.info("ℹ️ No YouTube channel connected. Videos will be generated but not uploaded. Connect in **Settings**.")

st.markdown("### 🎯 What video do you want to create?")
niche = st.text_input(
    "Niche / Topic (optional)",
    placeholder="e.g. personal finance tips, healthy recipes, true crime stories...",
    help="Leave blank to let the AI pick the #1 trending topic automatically"
)

st.markdown("---")
st.markdown("**What will happen:**")
st.markdown("""
1. 🔍 **CEO Agent** researches trending topics and creates a video plan
2. ✍️ **Script Polisher** refines the script for maximum engagement
3. 🎬 **Visual Generator** creates cinematic video clips with Sora AI
4. 🎤 **Audio Engineer** generates professional voiceovers
5. 🎞️ **Video Editor** assembles the final video with crossfades
6. 📈 **SEO Optimizer** writes titles, descriptions, and tags
7. 📤 **Uploader** publishes to your YouTube channel
""")

col1, col2 = st.columns(2)
with col1:
    st.markdown("**Estimated cost:** ~$3-5 per video")
with col2:
    st.markdown("**Estimated time:** ~20-30 minutes")

st.markdown("---")

if st.button("🚀 Generate Video", use_container_width=True, type="primary"):
    try:
        with httpx.Client(base_url=API_URL, timeout=15) as c:
            res = c.post("/api/jobs", json={"niche": niche}, headers=get_headers())
            data = res.json()

        if "job_id" in data:
            st.success(f"✅ Job queued! Job ID: `{data['job_id']}`")
            st.info("Go to the **Dashboard** tab to monitor progress in real-time.")
            if st.button("📊 Open Dashboard"):
                st.switch_page("pages/1_Dashboard.py")
        else:
            st.error(f"Failed to create job: {data}")
    except Exception as e:
        st.error(f"Error: {e}")
