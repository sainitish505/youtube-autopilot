"""
frontend/pages/3_My_Videos.py — Video library and job history.
Shows all completed jobs with thumbnails, YouTube links, and asset previews.
"""
import os
import streamlit as st
import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="My Videos | YouTube Autopilot", page_icon="🎥", layout="wide")

if not st.session_state.get("access_token"):
    st.warning("Please sign in first.")
    st.stop()


def get_headers():
    return {"Authorization": f"Bearer {st.session_state.access_token}"}


def fetch_jobs():
    try:
        with httpx.Client(base_url=API_URL, timeout=10) as c:
            return c.get("/api/jobs", headers=get_headers()).json()
    except Exception:
        return {"jobs": [], "total": 0}


def fetch_job_detail(job_id: str):
    try:
        with httpx.Client(base_url=API_URL, timeout=10) as c:
            return c.get(f"/api/jobs/{job_id}", headers=get_headers()).json()
    except Exception:
        return None


def cancel_job(job_id: str):
    try:
        with httpx.Client(base_url=API_URL, timeout=10) as c:
            return c.delete(f"/api/jobs/{job_id}", headers=get_headers()).json()
    except Exception:
        return {}


st.title("🎥 My Videos")
st.markdown("Browse your generated videos, download assets, and view YouTube links.")

data = fetch_jobs()
jobs = data.get("jobs", [])

if not jobs:
    st.info("No videos yet. Go to **New Video** to generate your first one!")
    st.stop()

# ── Filter tabs ────────────────────────────────────────────────────────────────
tab_all, tab_done, tab_running, tab_failed = st.tabs(["All", "✅ Completed", "🔄 In Progress", "❌ Failed"])

STATUS_ICON = {
    "queued": "📋",
    "running": "🔄",
    "completed": "✅",
    "failed": "❌",
    "cancelled": "🚫",
}

VOICE_LABELS = {"alloy": "Alloy", "echo": "Echo", "fable": "Fable", "onyx": "Onyx", "nova": "Nova", "shimmer": "Shimmer"}


def render_job_card(j: dict):
    """Render a single job card with details and actions."""
    status = j.get("status", "unknown")
    icon = STATUS_ICON.get(status, "❓")
    title = j.get("title") or j.get("niche") or "Untitled"
    cost = j.get("total_cost_usd", 0.0)
    created = str(j.get("created_at", ""))[:19]
    completed = str(j.get("completed_at", ""))[:19] if j.get("completed_at") else "—"
    video_url = j.get("video_url", "")
    scenes = j.get("scenes_count") or "—"
    error = j.get("error_message", "")

    with st.container():
        st.markdown(f"### {icon} {title}")

        col_meta, col_actions = st.columns([3, 1])
        with col_meta:
            cols = st.columns(4)
            cols[0].metric("Status", status.upper())
            cols[1].metric("Cost", f"${cost:.3f}")
            cols[2].metric("Scenes", scenes)
            cols[3].metric("Created", created.split("T")[0] if "T" in created else created)

            if completed != "—":
                st.caption(f"Completed: {completed}")

            if video_url:
                st.success(f"🎬 [Watch on YouTube]({video_url})", icon="🔗")

            if error:
                st.error(f"Error: {error}")

        with col_actions:
            job_id = j.get("id", "")
            if status in ("queued", "running"):
                if st.button("⏹ Cancel", key=f"cancel_{job_id}", use_container_width=True):
                    result = cancel_job(job_id)
                    st.toast("Job cancelled")
                    st.rerun()
            if status == "completed":
                if st.button("🔍 Details", key=f"details_{job_id}", use_container_width=True):
                    st.session_state[f"show_details_{job_id}"] = not st.session_state.get(f"show_details_{job_id}", False)

        # ── Expandable details ─────────────────────────────────────────────────
        if st.session_state.get(f"show_details_{job_id}", False) and status == "completed":
            detail = fetch_job_detail(job_id)
            if detail:
                assets = detail.get("assets", [])
                agents = detail.get("agents", [])

                if agents:
                    st.markdown("**Agent Pipeline:**")
                    agent_cols = st.columns(len(agents))
                    for i, a in enumerate(agents):
                        aname = a.get("agent_name", "")
                        astatus = a.get("status", "pending")
                        aicon = {"done": "✅", "running": "🔄", "failed": "❌", "pending": "⏳"}.get(astatus, "⏳")
                        with agent_cols[i]:
                            st.markdown(f"**{aicon} {aname}**\n\n`{astatus}`")

                def _is_web_url(u: str) -> bool:
                    return bool(u) and (u.startswith("http://") or u.startswith("https://"))

                thumbnails = [a for a in assets if a.get("type") in ("thumbnail", "image")]
                video_clips = [a for a in assets if a.get("type") == "video_clip"]
                audio_clips = [a for a in assets if a.get("type") == "audio"]

                if thumbnails:
                    st.markdown("**Thumbnail:**")
                    t = thumbnails[0]
                    url = t.get("url", "")
                    if _is_web_url(url):
                        st.image(url, width=400)
                    elif url.startswith("file://"):
                        local = url[7:]
                        st.caption(f"Thumbnail stored locally: `{local}`")
                    elif t.get("path"):
                        st.caption(f"Thumbnail path: `{t['path']}`")

                if video_clips:
                    st.markdown(f"**Video Clips ({len(video_clips)}):**")
                    for clip in video_clips[:3]:
                        url = clip.get("url", "")
                        if _is_web_url(url):
                            st.video(url)
                        elif url.startswith("file://"):
                            st.caption(f"Clip stored locally: `{url[7:]}`")
                        elif clip.get("path"):
                            st.caption(f"Clip R2 path: `{clip['path']}`")

                if audio_clips:
                    st.markdown(f"**Audio Clips ({len(audio_clips)}):**")
                    for clip in audio_clips[:3]:
                        url = clip.get("url", "")
                        if _is_web_url(url):
                            st.audio(url)
                        elif url.startswith("file://"):
                            st.caption(f"Audio stored locally: `{url[7:]}`")

        st.divider()


def filter_jobs(jobs: list, status_filter: list) -> list:
    return [j for j in jobs if j.get("status") in status_filter]


with tab_all:
    if not jobs:
        st.info("No jobs found.")
    else:
        for j in jobs:
            render_job_card(j)

with tab_done:
    done_jobs = filter_jobs(jobs, ["completed"])
    if not done_jobs:
        st.info("No completed videos yet.")
    else:
        st.markdown(f"**{len(done_jobs)} completed video(s)**")
        for j in done_jobs:
            render_job_card(j)

with tab_running:
    active_jobs = filter_jobs(jobs, ["queued", "running"])
    if not active_jobs:
        st.info("No active jobs.")
    else:
        st.markdown(f"**{len(active_jobs)} active job(s)**")
        for j in active_jobs:
            render_job_card(j)

with tab_failed:
    failed_jobs = filter_jobs(jobs, ["failed", "cancelled"])
    if not failed_jobs:
        st.success("No failed jobs! 🎉")
    else:
        st.markdown(f"**{len(failed_jobs)} failed/cancelled job(s)**")
        for j in failed_jobs:
            render_job_card(j)
