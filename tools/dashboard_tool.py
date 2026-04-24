"""
tools/dashboard_tool.py — DashboardTool

Writes agent status updates atomically to output/dashboard_state.json
so the Streamlit dashboard can display live progress.

Atomic write pattern: write to .tmp file, then os.replace() to avoid
partial reads by the dashboard.

Public helpers (can also be imported directly by other modules):
  update_status(agent, status, cost_so_far)
  add_asset(type, path)
  set_approval_pending(script)
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
logger = logging.getLogger(__name__)


def _default_state() -> Dict[str, Any]:
    return {
        "started_at": time.time(),
        "updated_at": time.time(),
        "agents": {},
        "total_cost": 0.0,
        "assets": [],
        "approval_pending": False,
        "pending_script": "",
        "log_lines": [],
        "youtube_url": "",
        "status": "running",
    }


def _load_state(state_path: str) -> Dict[str, Any]:
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return _default_state()


def _save_state(state_path: str, state: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    state["updated_at"] = time.time()
    tmp = state_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, state_path)


def _get_state_path() -> str:
    try:
        from config import get_config
        return get_config().dashboard_state_path
    except Exception:
        return os.path.join(BASE_DIR, "output", "dashboard_state.json")


# ── Module-level public helpers ───────────────────────────────────────────────

def update_status(agent: str, status: str, cost_so_far: float = 0.0) -> None:
    """Update a single agent's status. Status: pending|running|done|failed."""
    path = _get_state_path()
    state = _load_state(path)
    state["agents"][agent] = {
        "status": status,
        "updated_at": time.time(),
    }
    if cost_so_far > 0:
        state["total_cost"] = cost_so_far
    msg = f"[{agent}] → {status}"
    state["log_lines"].append({"ts": time.time(), "msg": msg})
    # Keep log to last 200 lines
    state["log_lines"] = state["log_lines"][-200:]
    _save_state(path, state)
    logger.info(msg)


def add_asset(asset_type: str, path: str) -> None:
    """Record a generated asset (video, image, audio, thumbnail)."""
    state_path = _get_state_path()
    state = _load_state(state_path)
    state["assets"].append({
        "type": asset_type,
        "path": path,
        "ts": time.time(),
    })
    _save_state(state_path, state)
    logger.info(f"Asset recorded: type={asset_type} path={path}")


def set_approval_pending(script: str) -> None:
    """Signal that a script is awaiting human approval in the dashboard."""
    path = _get_state_path()
    state = _load_state(path)
    state["approval_pending"] = True
    state["pending_script"] = script
    _save_state(path, state)
    logger.info("Approval set to pending in dashboard state.")


def clear_approval_pending() -> None:
    """Clear the approval pending flag after resolution."""
    path = _get_state_path()
    state = _load_state(path)
    state["approval_pending"] = False
    _save_state(path, state)


def set_youtube_url(url: str) -> None:
    """Record the final YouTube URL in dashboard state."""
    path = _get_state_path()
    state = _load_state(path)
    state["youtube_url"] = url
    state["status"] = "completed"
    _save_state(path, state)
    logger.info(f"YouTube URL recorded: {url}")


def set_pipeline_failed(reason: str) -> None:
    """Mark the pipeline as failed."""
    path = _get_state_path()
    state = _load_state(path)
    state["status"] = "failed"
    state["log_lines"].append({"ts": time.time(), "msg": f"PIPELINE FAILED: {reason}"})
    state["log_lines"] = state["log_lines"][-200:]
    _save_state(path, state)


# ── CrewAI Tool wrapper ───────────────────────────────────────────────────────

class DashboardInput(BaseModel):
    action: str = Field(
        description=(
            "Action to perform. One of: "
            "'update_status', 'add_asset', 'set_approval_pending', "
            "'set_youtube_url', 'log_message'."
        )
    )
    agent: Optional[str] = Field(default="", description="Agent name (for update_status).")
    status: Optional[str] = Field(default="", description="Agent status string.")
    cost_so_far: Optional[float] = Field(default=0.0, description="Cumulative cost so far.")
    asset_type: Optional[str] = Field(default="", description="Asset type (video/image/audio/thumbnail).")
    asset_path: Optional[str] = Field(default="", description="Absolute path to asset file.")
    script: Optional[str] = Field(default="", description="Script text (for set_approval_pending).")
    youtube_url: Optional[str] = Field(default="", description="YouTube URL (for set_youtube_url).")
    message: Optional[str] = Field(default="", description="Log message text.")


class DashboardTool(BaseTool):
    name: str = "Dashboard Updater"
    description: str = (
        "Updates the live Streamlit dashboard with agent status, cost, assets, and logs. "
        "Actions: update_status, add_asset, set_approval_pending, set_youtube_url, log_message. "
        "All writes are atomic — safe for concurrent access."
    )
    args_schema: Type[BaseModel] = DashboardInput

    def _run(
        self,
        action: str,
        agent: str = "",
        status: str = "",
        cost_so_far: float = 0.0,
        asset_type: str = "",
        asset_path: str = "",
        script: str = "",
        youtube_url: str = "",
        message: str = "",
    ) -> str:
        try:
            action = action.strip().lower()
            if action == "update_status":
                if not agent or not status:
                    return "ERROR: 'update_status' requires agent and status fields."
                update_status(agent, status, cost_so_far)
                return f"Dashboard updated: [{agent}] = {status}"

            elif action == "add_asset":
                if not asset_type or not asset_path:
                    return "ERROR: 'add_asset' requires asset_type and asset_path."
                add_asset(asset_type, asset_path)
                return f"Asset added: {asset_type} → {asset_path}"

            elif action == "set_approval_pending":
                if not script:
                    return "ERROR: 'set_approval_pending' requires script text."
                set_approval_pending(script)
                return "Dashboard approval flag set."

            elif action == "set_youtube_url":
                if not youtube_url:
                    return "ERROR: 'set_youtube_url' requires youtube_url."
                set_youtube_url(youtube_url)
                return f"YouTube URL set in dashboard: {youtube_url}"

            elif action == "log_message":
                path = _get_state_path()
                state = _load_state(path)
                state["log_lines"].append({"ts": time.time(), "msg": message})
                state["log_lines"] = state["log_lines"][-200:]
                _save_state(path, state)
                return f"Logged: {message}"

            else:
                return f"ERROR: Unknown dashboard action '{action}'."

        except Exception as e:
            logger.exception(f"DashboardTool failed: {e}")
            return f"ERROR: DashboardTool failed: {e}"
