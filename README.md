# YouTube Autopilot Agent v2

A fully autonomous, CEO-driven AI agent that researches trending niches, writes
full scene-by-scene scripts, generates videos with OpenAI Sora, assembles them
with MoviePy, and uploads to YouTube — all from a single command.

---

## What's New in v2

| Feature | v1 | v2 |
|---------|----|----|
| Architecture | 4 sequential agents | CEO orchestrator + 6 dynamic sub-crews |
| Script | Single short prompt | Full scene-by-scene script with voiceover |
| Approval flow | None | Console + Streamlit dashboard approval queue |
| Cost estimate | None | Pre-production cost breakdown with approve/reject |
| Video length | 8-second Shorts only | 1–10 minutes (configurable) |
| Video editing | None | MoviePy assembly with crossfades + background music |
| TTS voiceover | None | OpenAI TTS per scene |
| Thumbnail | None | DALL-E 3 auto-generated |
| Live dashboard | None | Streamlit real-time status + asset preview |
| Config | Hardcoded | config.yaml + .env |

---

## Architecture

```
python main.py [--niche "topic"] [--dashboard]
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│                    CEO Agent (GPT-4o)                      │
│   ┌─────────────────────────────────────────────────┐     │
│   │  1. TrendResearchTool   → trending niche ideas  │     │
│   │  2. CostEstimatorTool   → cost breakdown        │     │
│   │  3. ScriptApproverTool  → human/auto approval   │     │
│   └─────────────────────────────────────────────────┘     │
│   OUTPUT: VideoPlan (Pydantic) — JSON plan with scenes     │
└───────────────────────┬───────────────────────────────────┘
                        │  plan dict
                        ▼
┌───────────────────────────────────────────────────────────┐
│                  CrewFactory.build_and_run()               │
│                                                           │
│  ScriptPolisher  →  VisualGenerator  →  AudioEngineer     │
│       (mini)            (Sora)            (TTS)           │
│                                                           │
│  VideoEditor  →  SEOOptimizer  →  Uploader                │
│   (MoviePy)       (mini)        (YouTube API)             │
└───────────────────────────────────────────────────────────┘
                        │
                        ▼
              YouTube URL  +  Dashboard update
```

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- OpenAI account with credits (GPT-4o, Sora-2, TTS, DALL-E 3)
- Google Cloud project with YouTube Data API v3 enabled
- `client_secrets.json` (Google OAuth2 Desktop app credential)

### 2. Install

```bash
cd youtube_agent
python3.11 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# System dependency (required by MoviePy)
# macOS:   brew install ffmpeg
# Ubuntu:  sudo apt install ffmpeg
# Windows: https://ffmpeg.org/download.html
```

### 3. Configure

`.env` (already present — do not edit):
```
OPENAI_API_KEY=sk-proj-...
GEMINI_API_KEY=...
```

`config.yaml` (edit to customise):
```yaml
autonomous_mode: true          # false = wait for human approval
max_video_minutes: 10
default_niche: ""              # blank = auto-detect trending
human_approval_timeout: 300    # seconds to wait for approval
video_model: "sora-2"
tts_voice: "alloy"
upload_privacy: "public"
auto_approve_under_dollars: 2.0
```

### 4. Run

```bash
# Basic run (autonomous, auto-detect niche)
python main.py

# With specific niche
python main.py --niche "quantum computing explained"

# With live dashboard at http://localhost:8501
python main.py --dashboard

# Dashboard only (monitor a running agent)
streamlit run dashboard.py
```

---

## File Structure

```
youtube_agent/
├── main.py                        # Entry point
├── crew.py                        # CEO crew + VideoPlan Pydantic model
├── config.py                      # Config loader (dataclass)
├── config.yaml                    # All tunable settings
├── dashboard.py                   # Streamlit live dashboard
├── requirements.txt
├── .env                           # API keys (do not commit)
├── client_secrets.json            # Google OAuth (do not commit)
├── token.pickle                   # Auto-generated after first auth
│
├── agents/
│   ├── __init__.py
│   ├── ceo_agent.py               # CEO Agent definition (GPT-4o)
│   └── crew_factory.py            # Dynamic sub-crew builder + runner
│
├── tools/
│   ├── __init__.py
│   ├── trend_research.py          # TrendResearchTool
│   ├── cost_estimator.py          # CostEstimatorTool
│   ├── script_approver.py         # ScriptApproverTool
│   ├── media_generator.py         # MediaGeneratorTool (video/image/tts/thumbnail)
│   ├── video_editor.py            # VideoEditorTool (MoviePy)
│   ├── dashboard_tool.py          # DashboardTool (state writer)
│   ├── veo_tool.py                # Original Sora tool (kept)
│   └── youtube_uploader.py        # YouTube upload (kept)
│
├── output/
│   ├── videos/                    # Generated MP4 clips + final video
│   ├── images/                    # DALL-E generated images
│   ├── audio/                     # TTS voiceover MP3s
│   ├── thumbnails/                # Thumbnail PNGs
│   ├── dashboard_state.json       # Live state for dashboard
│   └── approvals.json             # Approval queue
│
└── logs/
    └── run_YYYYMMDD_HHMMSS.log    # Timestamped run logs
```

---

## Config Options

| Key | Default | Description |
|-----|---------|-------------|
| `autonomous_mode` | `true` | Skip human approval prompts |
| `max_video_minutes` | `10` | Maximum video length in minutes |
| `default_niche` | `""` | Lock to a niche; blank = auto-detect |
| `human_approval_timeout` | `300` | Seconds before auto-approve |
| `video_model` | `sora-2` | OpenAI video model |
| `tts_voice` | `alloy` | OpenAI TTS voice (alloy/echo/fable/onyx/nova/shimmer) |
| `upload_privacy` | `public` | YouTube privacy (public/unlisted/private) |
| `auto_approve_under_dollars` | `2.0` | Auto-approve if cost < this value |
| `video_resolution` | `1920x1080` | Default video resolution |
| `short_resolution` | `720x1280` | Vertical Short resolution |
| `crossfade_duration` | `0.5` | Seconds of crossfade between scenes |
| `background_music_volume` | `0.20` | Background music volume (0.0–1.0) |
| `log_level` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |

---

## Cost Breakdown

Costs per 5-minute video (10 scenes × 8s clips):

| Component | Rate | Est. Cost |
|-----------|------|-----------|
| GPT-4o (CEO, ~2K tokens) | $0.005/1K tokens | $0.01 |
| GPT-4o-mini (6 agents × 2K tokens) | $0.00015/1K tokens | $0.002 |
| Sora-2 (10 × 8s clips) | $0.30/clip | $3.00 |
| OpenAI TTS (~1,500 chars) | $0.015/1K chars | $0.02 |
| DALL-E 3 thumbnail | $0.04/image (HD) | $0.08 |
| YouTube upload | Free | $0.00 |
| **Total** | | **~$3.11** |

For Shorts (1 clip, 8s), total cost drops to ~$0.35.

---

## How the Dashboard Works

The Streamlit dashboard reads `output/dashboard_state.json` every 2 seconds.
Each agent writes its status via `DashboardTool` using atomic file replacement
(write → `.tmp` → `os.replace()`) to avoid partial reads.

Dashboard features:
- Per-agent status cards (Pending / Running / Done / Failed) with timestamps
- Running cost tracker
- Generated asset previews (inline video player, image gallery, audio player)
- Script approval queue — APPROVE / REQUEST EDIT / REJECT buttons write to `output/approvals.json`
- Live log tail from the latest run log
- "Run Agent" button to launch a new pipeline run

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: crewai` | Run `pip install -r requirements.txt` inside venv |
| `ModuleNotFoundError: moviepy` | Run `pip install moviepy>=1.0.3` |
| `ffmpeg not found` | Install ffmpeg system package (see Quick Start) |
| `429 RESOURCE_EXHAUSTED` | OpenAI rate limit — wait and retry, or reduce num_ideas |
| `Error 403: access_denied` (YouTube) | Add your email as a test user in OAuth consent screen |
| `Error 400: redirect_uri_mismatch` | Use a Desktop app OAuth credential, not Web app |
| `client_secrets.json not found` | Save your Google OAuth JSON as `client_secrets.json` |
| Sora `status != completed` | Sora quota or content policy issue — revise the prompt |
| Dashboard not loading | Run `streamlit run dashboard.py` manually |
| `EDIT: ...` loop | CEO will revise until APPROVED — check autonomous_mode in config.yaml |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Agent framework | CrewAI |
| Orchestrator LLM | OpenAI GPT-4o |
| Sub-agent LLM | OpenAI GPT-4o-mini |
| Video generation | OpenAI Sora-2 |
| TTS voiceover | OpenAI TTS (tts-1) |
| Image / Thumbnail | OpenAI DALL-E 3 |
| Video editing | MoviePy + ffmpeg |
| YouTube upload | Google YouTube Data API v3 |
| Dashboard | Streamlit |
| Auth | OAuth 2.0 (InstalledAppFlow) |
| Language | Python 3.11 |
