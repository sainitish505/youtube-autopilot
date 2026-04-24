"""
frontend/pages/1_Dashboard.py — Live per-user pipeline status dashboard.
Polls the FastAPI /api/jobs endpoint every 3 seconds while a job is running.
"""
import os
import time
import streamlit as st
import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Dashboard | YouTube Autopilot", page_icon="📊", layout="wide")

if not st.session_state.get("access_token"):
    st.warning("Please sign in first.")
    st.stop()

AGENT_ORDER = ["CEO", "ScriptPolisher", "VisualGenerator", "AudioEngineer", "VideoEditor", "SEOOptimizer", "Uploader"]
STATUS_ICON = {"pending": "⏳", "running": "🔄", "done": "✅", "failed": "❌", "queued": "📋", "completed": "✅"}
STATUS_COLOR = {"pending": "#6c7086", "running": "#f9e2af", "done": "#a6e3a1", "failed": "#f38ba8", "completed": "#a6e3a1"}


def get_headers():
    return {"Authorization": f"Bearer {st.session_state.access_token}"}


def fetch_jobs():
    try:
        with httpx.Client(base_url=API_URL, timeout=10) as c:
            return c.get("/api/jobs", headers=get_headers()).json()
    except Exception:
        return {"jobs": [], "total": 0}


def fetch_job(job_id):
    try:
        with httpx.Client(base_url=API_URL, timeout=10) as c:
            return c.get(f"/api/jobs/{job_id}", headers=get_headers()).json()
    except Exception:
        return None


st.title("📊 Live Dashboard")
st.markdown("Real-time pipeline status for your video generation jobs.")

jobs_data = fetch_jobs()
jobs = jobs_data.get("jobs", [])

if not jobs:
    st.info("No jobs yet. Go to **New Video** to generate your first video!")
else:
    active = [j for j in jobs if j["status"] in ("queued", "running")]

    if active:
        st.markdown("### 🔄 Active Jobs")
        job_detail = fetch_job(active[0]["id"])
        if job_detail:
            job = job_detail
            st.markdown(f"**{job.get('title') or job.get('niche') or 'Generating...'}**")

            agents = job.get("agents", [])
            agent_map = {a["agent_name"]: a for a in agents}

            cols = st.columns(len(AGENT_ORDER))
            for i, agent in enumerate(AGENT_ORDER):
                a = agent_map.get(agent, {"status": "pending"})
                color = STATUS_COLOR.get(a["status"], "#6c7086")
                icon = STATUS_ICON.get(a["status"], "⏳")
                with cols[i]:
                    st.markdown(f"""
                    <div style="background:#1e1e2e;border-radius:8px;padding:12px;text-align:center;border-left:3px solid {color}">
                        <div style="font-size:1.5rem">{icon}</div>
                        <div style="font-size:0.75rem;color:#cdd6f4">{agent}</div>
                        <div style="font-size:0.7rem;color:{color}">{a['status'].upper()}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown(f"**Cost so far:** ${job.get('total_cost_usd', 0.0):.3f}")

            if job.get("video_url"):
                st.success(f"✅ Video published! [{job['video_url']}]({job['video_url']})")

            # Assets
            assets = job.get("assets", [])
            if assets:
                st.markdown("### 🎞️ Generated Assets")
                for asset in assets:
                    url = asset.get("url", "")
                    atype = asset.get("type", "")
                    if url and not url.startswith("file://"):
                        if atype == "video_clip":
                            st.video(url)
                        elif atype == "audio":
                            st.audio(url)
                        elif atype in ("thumbnail", "image"):
                            st.image(url, width=300)

            time.sleep(3)
            st.rerun()

    st.markdown("### 📋 Recent Jobs")
    for j in jobs[:10]:
        icon = STATUS_ICON.get(j["status"], "❓")
        cost = f"${j['total_cost_usd']:.2f}"
        title = j.get("title") or j.get("niche") or "Untitled"
        url = j.get("video_url", "")

        with st.expander(f"{icon} {title} — {j['status'].upper()} | {cost}"):
            st.markdown(f"**Job ID:** `{j['id']}`")
            st.markdown(f"**Created:** {str(j['created_at'])[:19]}")
            if url:
                st.markdown(f"**YouTube URL:** [{url}]({url})")
            if j.get("error_message"):
                st.error(j["error_message"])
