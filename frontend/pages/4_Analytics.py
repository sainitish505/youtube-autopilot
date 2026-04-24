"""
frontend/pages/4_Analytics.py — Per-user cost and usage analytics.

Displays:
  - Total videos, costs, success rate (top metrics)
  - Monthly cost trend (bar chart)
  - Cost breakdown by AI service (Sora, TTS, DALL-E, GPT-4o)
  - Most used niches (horizontal bar)
  - Recent analytics events table
"""
import os
import streamlit as st
import httpx
import pandas as pd
from datetime import datetime

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Analytics | YouTube Autopilot", page_icon="📈", layout="wide")

if not st.session_state.get("access_token"):
    st.warning("Please sign in first.")
    st.stop()


def get_headers():
    return {"Authorization": f"Bearer {st.session_state.access_token}"}


def fetch_summary():
    try:
        with httpx.Client(base_url=API_URL, timeout=10) as c:
            return c.get("/api/analytics/summary", headers=get_headers()).json()
    except Exception:
        return {}


def fetch_events():
    try:
        with httpx.Client(base_url=API_URL, timeout=10) as c:
            return c.get("/api/analytics/events", headers=get_headers()).json()
    except Exception:
        return {"events": []}


def fetch_jobs():
    try:
        with httpx.Client(base_url=API_URL, timeout=10) as c:
            return c.get("/api/jobs", headers=get_headers()).json()
    except Exception:
        return {"jobs": []}


st.title("📈 Analytics")
st.markdown("Track your AI spending, success rates, and content performance.")

summary = fetch_summary()
events_data = fetch_events()
jobs_data = fetch_jobs()

# ── Top metrics ───────────────────────────────────────────────────────────────
st.markdown("### Overview")
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Total Videos", summary.get("total_videos", 0))
with col2:
    st.metric("Total Spend", f"${summary.get('total_cost_usd', 0.0):.2f}")
with col3:
    st.metric("Success Rate", f"{summary.get('success_rate', 0.0):.1f}%")
with col4:
    st.metric("This Month", summary.get("videos_this_month", 0))
with col5:
    avg = summary.get("avg_cost_per_video", 0.0)
    st.metric("Avg Cost/Video", f"${avg:.2f}")

st.markdown("---")

# ── Monthly costs ─────────────────────────────────────────────────────────────
jobs = jobs_data.get("jobs", [])

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("### 📊 Cost by AI Service")
    cost_by_type = summary.get("cost_by_type", {})
    if cost_by_type:
        # Map internal event types to friendly names
        label_map = {
            "sora_generate": "Sora (Video)",
            "tts_generate": "TTS (Voice)",
            "dalle_generate": "DALL-E (Images)",
            "gpt4o_call": "GPT-4o (LLM)",
        }
        df_cost = pd.DataFrame([
            {"Service": label_map.get(k, k), "Cost ($)": round(v, 4)}
            for k, v in cost_by_type.items()
            if v > 0
        ])
        if not df_cost.empty:
            df_cost = df_cost.sort_values("Cost ($)", ascending=False)
            st.bar_chart(df_cost.set_index("Service"))
        else:
            st.info("No cost data by service yet.")
    else:
        st.info("No cost breakdown available yet. Generate some videos to see spending.")

with col_right:
    st.markdown("### 🎯 Top Niches")
    videos_by_niche = summary.get("videos_by_niche", {})
    if videos_by_niche:
        df_niche = pd.DataFrame([
            {"Niche": k, "Videos": v}
            for k, v in list(videos_by_niche.items())[:10]
        ])
        df_niche = df_niche.sort_values("Videos", ascending=False)
        st.bar_chart(df_niche.set_index("Niche"))
    else:
        st.info("Generate videos across different niches to see your content mix.")

st.markdown("---")

# ── Monthly cost trend ────────────────────────────────────────────────────────
if jobs:
    st.markdown("### 📅 Monthly Cost Trend")
    try:
        df_jobs = pd.DataFrame([
            {
                "month": pd.to_datetime(j["created_at"]).strftime("%Y-%m") if j.get("created_at") else "unknown",
                "cost": j.get("total_cost_usd", 0.0),
                "status": j.get("status", ""),
            }
            for j in jobs if j.get("created_at")
        ])
        if not df_jobs.empty:
            monthly = df_jobs.groupby("month")["cost"].sum().reset_index()
            monthly.columns = ["Month", "Total Cost ($)"]
            monthly = monthly.sort_values("Month")
            st.bar_chart(monthly.set_index("Month"))
    except Exception as e:
        st.warning(f"Could not render trend chart: {e}")

# ── Job success/failure breakdown ─────────────────────────────────────────────
if jobs:
    st.markdown("### ✅ Job Status Breakdown")
    status_counts = {}
    for j in jobs:
        s = j.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    if status_counts:
        df_status = pd.DataFrame([
            {"Status": k.capitalize(), "Count": v}
            for k, v in status_counts.items()
        ])
        st.bar_chart(df_status.set_index("Status"))

st.markdown("---")

# ── Recent events table ───────────────────────────────────────────────────────
events = events_data.get("events", [])
if events:
    st.markdown("### 🕐 Recent API Events")
    df_events = pd.DataFrame([
        {
            "Type": e.get("type", ""),
            "Cost ($)": round(e.get("cost_usd", 0.0), 6),
            "Tokens": e.get("tokens", 0),
            "Time": str(e.get("ts", ""))[:19],
        }
        for e in events[:50]
    ])
    st.dataframe(df_events, use_container_width=True, hide_index=True)

    total_events_cost = sum(e.get("cost_usd", 0.0) for e in events)
    st.caption(f"Showing last {len(events)} events — total cost: ${total_events_cost:.4f}")
else:
    st.info("No detailed API events recorded yet. Events are tracked during pipeline runs.")

# ── This month summary card ───────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 💰 This Month Summary")
m_col1, m_col2, m_col3 = st.columns(3)
with m_col1:
    st.metric("Videos Generated", summary.get("videos_this_month", 0))
with m_col2:
    st.metric("Total Spent", f"${summary.get('cost_this_month_usd', 0.0):.2f}")
with m_col3:
    vpm = summary.get("videos_this_month", 0)
    cpm = summary.get("cost_this_month_usd", 0.0)
    avg_m = cpm / vpm if vpm > 0 else 0.0
    st.metric("Avg Cost This Month", f"${avg_m:.2f}")
