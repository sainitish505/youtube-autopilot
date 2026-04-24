"""
frontend/components/job_card.py — Reusable job status card component.

Usage:
    from frontend.components.job_card import render_agent_pipeline, render_job_summary
"""
import streamlit as st
from typing import List, Dict, Any

AGENT_ORDER = ["CEO", "ScriptPolisher", "VisualGenerator", "AudioEngineer", "VideoEditor", "SEOOptimizer", "Uploader"]

STATUS_ICON = {
    "pending": "⏳",
    "running": "🔄",
    "done": "✅",
    "failed": "❌",
    "queued": "📋",
    "completed": "✅",
    "cancelled": "🚫",
}

STATUS_COLOR = {
    "pending": "#6c7086",
    "running": "#f9e2af",
    "done": "#a6e3a1",
    "failed": "#f38ba8",
    "completed": "#a6e3a1",
    "queued": "#89b4fa",
    "cancelled": "#9399b2",
}


def render_agent_pipeline(agents: List[Dict[str, Any]]):
    """
    Render a row of agent status cards.

    Parameters
    ----------
    agents : list of dicts with keys: agent_name, status
    """
    agent_map = {a.get("agent_name", ""): a for a in agents}
    cols = st.columns(len(AGENT_ORDER))
    for i, name in enumerate(AGENT_ORDER):
        a = agent_map.get(name, {"status": "pending"})
        status = a.get("status", "pending")
        color = STATUS_COLOR.get(status, "#6c7086")
        icon = STATUS_ICON.get(status, "⏳")
        with cols[i]:
            st.markdown(
                f"""
                <div style="
                    background:#1e1e2e;
                    border-radius:8px;
                    padding:10px 8px;
                    text-align:center;
                    border-left:3px solid {color};
                    min-height:80px;
                ">
                    <div style="font-size:1.4rem">{icon}</div>
                    <div style="font-size:0.72rem;color:#cdd6f4;margin-top:4px">{name}</div>
                    <div style="font-size:0.65rem;color:{color};margin-top:2px">{status.upper()}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_job_summary(job: Dict[str, Any]):
    """
    Render a compact job summary row (used in lists).

    Parameters
    ----------
    job : dict with keys: id, status, title, niche, total_cost_usd, created_at, video_url
    """
    status = job.get("status", "unknown")
    icon = STATUS_ICON.get(status, "❓")
    title = job.get("title") or job.get("niche") or "Untitled"
    cost = job.get("total_cost_usd", 0.0)
    created = str(job.get("created_at", ""))[:10]
    url = job.get("video_url", "")

    col1, col2, col3, col4 = st.columns([4, 2, 2, 2])
    with col1:
        st.markdown(f"**{icon} {title}**")
    with col2:
        st.markdown(f"`{status.upper()}`")
    with col3:
        st.markdown(f"`${cost:.3f}`")
    with col4:
        if url:
            st.markdown(f"[▶ Watch]({url})")
        else:
            st.markdown(created)
