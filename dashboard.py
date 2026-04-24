"""
dashboard.py — Streamlit Live Dashboard for YouTube Autopilot Agent v2

Reads output/dashboard_state.json every 2 seconds and displays:
  - Agent status cards (Pending / Running / Done / Failed)
  - Running cost tracker
  - Generated assets (video, images, audio, thumbnails)
  - Script approval queue
  - Live log tail
  - Run again button

Run standalone:
    streamlit run dashboard.py

Or launch automatically via:
    python main.py --dashboard
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# ── Path setup ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
STATE_PATH = os.path.join(OUTPUT_DIR, "dashboard_state.json")
APPROVALS_PATH = os.path.join(OUTPUT_DIR, "approvals.json")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

REFRESH_INTERVAL = 2  # seconds

# ── Status colour map ─────────────────────────────────────────────────────────
STATUS_COLORS = {
    "pending":  "#6b7280",  # gray
    "running":  "#f59e0b",  # amber
    "done":     "#10b981",  # green
    "failed":   "#ef4444",  # red
    "":         "#6b7280",
}

STATUS_EMOJI = {
    "pending":  "⏳",
    "running":  "🔄",
    "done":     "✅",
    "failed":   "❌",
    "":         "⏳",
}

AGENT_ORDER = [
    "CEO",
    "ScriptPolisher",
    "VisualGenerator",
    "AudioEngineer",
    "VideoEditor",
    "SEOOptimizer",
    "Uploader",
]

AGENT_LABELS = {
    "CEO":              "CEO / Orchestrator",
    "ScriptPolisher":   "Script Polisher",
    "VisualGenerator":  "Visual Generator (Sora)",
    "AudioEngineer":    "Audio Engineer (TTS)",
    "VideoEditor":      "Video Editor",
    "SEOOptimizer":     "SEO Optimizer",
    "Uploader":         "YouTube Uploader",
}


# ── Data helpers ──────────────────────────────────────────────────────────────

def load_state() -> Dict[str, Any]:
    """Load dashboard state JSON, returning defaults if not found."""
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "started_at": None,
        "updated_at": None,
        "agents": {},
        "total_cost": 0.0,
        "assets": [],
        "approval_pending": False,
        "pending_script": "",
        "log_lines": [],
        "youtube_url": "",
        "status": "idle",
    }


def write_approval(status: str, edit_instructions: str = "") -> None:
    """Write an approval decision to approvals.json."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    payload = {
        "timestamp": time.time(),
        "status": status,
        "edit_instructions": edit_instructions,
    }
    tmp = APPROVALS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, APPROVALS_PATH)


def get_latest_log_file() -> Optional[str]:
    """Return the path to the most recent log file."""
    logs = sorted(Path(LOGS_DIR).glob("run_*.log"), key=os.path.getmtime, reverse=True)
    return str(logs[0]) if logs else None


def tail_log(path: str, n: int = 50) -> List[str]:
    """Return the last n lines of a log file."""
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return [l.rstrip() for l in lines[-n:]]
    except Exception:
        return []


def format_elapsed(ts: Optional[float]) -> str:
    if ts is None:
        return "—"
    elapsed = time.time() - ts
    if elapsed < 60:
        return f"{elapsed:.0f}s"
    elif elapsed < 3600:
        return f"{elapsed/60:.1f}m"
    return f"{elapsed/3600:.1f}h"


def format_ts(ts: Optional[float]) -> str:
    if ts is None:
        return "—"
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="YouTube Autopilot Agent",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
  .agent-card {
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 8px;
    border-left: 4px solid #6b7280;
    background: #1e1e2e;
    color: #cdd6f4;
  }
  .agent-card.running  { border-left-color: #f59e0b; }
  .agent-card.done     { border-left-color: #10b981; }
  .agent-card.failed   { border-left-color: #ef4444; }
  .agent-card.pending  { border-left-color: #6b7280; }
  .cost-badge {
    font-size: 2rem;
    font-weight: bold;
    color: #f59e0b;
  }
  .url-box {
    background: #1e1e2e;
    padding: 12px 20px;
    border-radius: 8px;
    border: 1px solid #10b981;
    font-size: 1.1rem;
  }
  .log-box {
    background: #0d0d1a;
    padding: 10px;
    border-radius: 6px;
    font-family: monospace;
    font-size: 0.78rem;
    max-height: 300px;
    overflow-y: auto;
    color: #a6adc8;
  }
  .script-box {
    background: #1e1e2e;
    padding: 14px;
    border-radius: 8px;
    white-space: pre-wrap;
    font-family: monospace;
    font-size: 0.82rem;
    max-height: 400px;
    overflow-y: auto;
    color: #cdd6f4;
  }
  h1.hero { font-size: 2rem; font-weight: 800; margin-bottom: 0; }
  .sub-hero { color: #6c7086; margin-top: 0; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)


# ── Main render ───────────────────────────────────────────────────────────────

def render_dashboard():
    state = load_state()

    # Header
    col_title, col_status = st.columns([4, 1])
    with col_title:
        st.markdown('<h1 class="hero">🎬 YouTube Autopilot Agent</h1>', unsafe_allow_html=True)
        st.markdown('<p class="sub-hero">CEO-Driven Autonomous Video Production — Live Dashboard</p>',
                    unsafe_allow_html=True)
    with col_status:
        pipeline_status = state.get("status", "idle")
        status_colors = {"running": "🟡", "completed": "🟢", "failed": "🔴", "idle": "⚪"}
        st.metric("Pipeline", f"{status_colors.get(pipeline_status, '⚪')} {pipeline_status.capitalize()}")
        started = state.get("started_at")
        if started:
            st.caption(f"Started {format_ts(started)} · Elapsed {format_elapsed(started)}")

    st.divider()

    # ── Main layout: left (agents + cost) | right (assets + logs) ─────────────
    left_col, right_col = st.columns([1, 1])

    with left_col:
        # Agent status cards
        st.subheader("Agent Pipeline")
        agents = state.get("agents", {})
        for agent_key in AGENT_ORDER:
            info = agents.get(agent_key, {})
            status = info.get("status", "pending")
            label = AGENT_LABELS.get(agent_key, agent_key)
            emoji = STATUS_EMOJI.get(status, "⏳")
            updated = info.get("updated_at")
            ts_str = format_ts(updated) if updated else "—"

            card_class = f"agent-card {status}"
            st.markdown(
                f'<div class="{card_class}">'
                f'<b>{emoji} {label}</b> '
                f'<span style="float:right;font-size:0.8rem;color:#6c7086">{status.upper()} · {ts_str}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Cost tracker
        st.subheader("Cost Tracker")
        total_cost = state.get("total_cost", 0.0)
        st.markdown(f'<div class="cost-badge">${total_cost:.4f}</div>', unsafe_allow_html=True)
        st.caption("Estimated API spend so far")

        # YouTube URL
        youtube_url = state.get("youtube_url", "")
        if youtube_url:
            st.success("Video Published!")
            st.markdown(
                f'<div class="url-box">📺 <a href="{youtube_url}" target="_blank">{youtube_url}</a></div>',
                unsafe_allow_html=True,
            )

    with right_col:
        # Generated assets
        st.subheader("Generated Assets")
        assets = state.get("assets", [])
        if not assets:
            st.caption("No assets generated yet.")
        else:
            asset_tabs_labels = []
            video_assets = [a for a in assets if a.get("type") in ("video", "video_clip", "final_video")]
            image_assets = [a for a in assets if a.get("type") in ("image", "thumbnail")]
            audio_assets = [a for a in assets if a.get("type") == "audio"]

            tab_names = []
            if video_assets:
                tab_names.append("Videos")
            if image_assets:
                tab_names.append("Images")
            if audio_assets:
                tab_names.append("Audio")

            if tab_names:
                tabs = st.tabs(tab_names)
                tab_idx = 0

                if video_assets and tab_idx < len(tabs):
                    with tabs[tab_idx]:
                        for a in video_assets[-3:]:  # show last 3
                            p = a.get("path", "")
                            if p and os.path.exists(p):
                                st.video(p)
                                st.caption(os.path.basename(p))
                    tab_idx += 1

                if image_assets and tab_idx < len(tabs):
                    with tabs[tab_idx]:
                        img_cols = st.columns(min(len(image_assets), 3))
                        for i, a in enumerate(image_assets[-6:]):
                            p = a.get("path", "")
                            if p and os.path.exists(p):
                                with img_cols[i % len(img_cols)]:
                                    st.image(p, caption=os.path.basename(p), use_column_width=True)
                    tab_idx += 1

                if audio_assets and tab_idx < len(tabs):
                    with tabs[tab_idx]:
                        for a in audio_assets[-5:]:
                            p = a.get("path", "")
                            if p and os.path.exists(p):
                                st.audio(p)
                                st.caption(os.path.basename(p))

        # Live log
        st.subheader("Live Log")
        log_lines = state.get("log_lines", [])
        if log_lines:
            log_text = "\n".join(
                f"{format_ts(line.get('ts'))}  {line.get('msg', '')}"
                for line in log_lines[-40:]
            )
            st.markdown(f'<div class="log-box">{log_text}</div>', unsafe_allow_html=True)
        else:
            # Fallback: read from log file
            log_file = get_latest_log_file()
            if log_file:
                lines = tail_log(log_file, n=30)
                if lines:
                    log_text = "\n".join(lines)
                    st.markdown(f'<div class="log-box">{log_text}</div>', unsafe_allow_html=True)
                else:
                    st.caption("No log entries yet.")
            else:
                st.caption("No log file found.")

    st.divider()

    # ── Approval queue ────────────────────────────────────────────────────────
    approval_pending = state.get("approval_pending", False)
    if approval_pending:
        st.subheader("📋 Script Approval Queue")
        st.warning("A script is awaiting your approval before production begins.")

        pending_script = state.get("pending_script", "")
        if pending_script:
            st.markdown('<div class="script-box">' + pending_script.replace("\n", "<br>") + "</div>",
                        unsafe_allow_html=True)
        else:
            st.caption("(Script text not available)")

        approve_col, edit_col, reject_col = st.columns([1, 2, 1])

        with approve_col:
            if st.button("✅ APPROVE", type="primary", use_container_width=True):
                write_approval("dashboard_approved")
                st.success("Approved! Production will continue.")
                st.rerun()

        with edit_col:
            edit_text = st.text_input("Edit instructions (optional):", key="edit_instructions")
            if st.button("✏️ REQUEST EDIT", use_container_width=True):
                instr = edit_text.strip() or "Please improve the script and make it more engaging."
                write_approval("dashboard_edit", edit_instructions=instr)
                st.info(f"Edit requested: {instr}")
                st.rerun()

        with reject_col:
            if st.button("❌ REJECT", use_container_width=True):
                write_approval("dashboard_rejected")
                st.error("Script rejected. Pipeline will abort.")
                st.rerun()

    # ── Bottom controls ───────────────────────────────────────────────────────
    st.divider()
    bottom_left, bottom_right = st.columns([2, 1])

    with bottom_left:
        st.caption(f"Last updated: {format_ts(state.get('updated_at'))}  ·  Auto-refresh every {REFRESH_INTERVAL}s")

    with bottom_right:
        run_col, refresh_col = st.columns(2)
        with run_col:
            if st.button("▶ Run Agent", use_container_width=True):
                _launch_agent_background()
                st.success("Agent launched! Refresh in a moment.")
        with refresh_col:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()

    # ── Auto-refresh ──────────────────────────────────────────────────────────
    if state.get("status") in ("running", "idle"):
        time.sleep(REFRESH_INTERVAL)
        st.rerun()


def _launch_agent_background():
    """Launch the main agent pipeline as a background subprocess."""
    main_path = os.path.join(BASE_DIR, "main.py")
    try:
        subprocess.Popen(
            [sys.executable, main_path],
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        st.error(f"Could not launch agent: {e}")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__" or True:
    render_dashboard()
