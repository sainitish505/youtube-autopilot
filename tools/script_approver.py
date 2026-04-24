"""
tools/script_approver.py — ScriptApproverTool

Presents the full script to the user for review.
- If autonomous_mode is True: auto-approves immediately.
- Otherwise: waits up to HUMAN_APPROVAL_TIMEOUT seconds for:
    APPROVE         → returns "APPROVED"
    EDIT: <changes> → returns the edit instructions so the CEO can revise
  Times out → auto-approves.

Also writes the pending approval state to output/approvals.json so the
Streamlit dashboard can show it.
"""

import json
import logging
import os
import sys
import textwrap
import time
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
logger = logging.getLogger(__name__)


class ScriptApproverInput(BaseModel):
    script_text: str = Field(
        description=(
            "The full video script text to show the user for approval. "
            "May include scene breakdown, voiceover lines, and descriptions."
        )
    )


class ScriptApproverTool(BaseTool):
    name: str = "Script Approver"
    description: str = (
        "Presents the script to the human operator for review. "
        "Returns 'APPROVED' if the user approves, or 'EDIT: <instructions>' "
        "if they want changes. Auto-approves in autonomous mode or on timeout."
    )
    args_schema: Type[BaseModel] = ScriptApproverInput

    def _run(self, script_text: str) -> str:
        try:
            from config import get_config
            cfg = get_config()
            autonomous = cfg.autonomous_mode
            timeout = cfg.human_approval_timeout
            approvals_path = cfg.approvals_path
        except Exception:
            autonomous = True
            timeout = 300
            approvals_path = os.path.join(BASE_DIR, "output", "approvals.json")

        if autonomous:
            logger.info("ScriptApproverTool: autonomous_mode=True — auto-approving script.")
            _write_approval_state(approvals_path, script_text, status="auto_approved")
            return "APPROVED"

        # ── Display the script ─────────────────────────────────────────────────
        _print_script(script_text)
        _write_approval_state(approvals_path, script_text, status="pending")

        print("\n" + "=" * 70)
        print("  SCRIPT APPROVAL REQUIRED")
        print("  Options:")
        print("    APPROVE                  — proceed with this script")
        print("    EDIT: <your instructions>— revise the script (CEO will rewrite)")
        print(f"  (Auto-approves in {timeout}s)\n")
        print("  > ", end="", flush=True)

        result = _wait_for_response(timeout_seconds=timeout)

        if result.startswith("EDIT:"):
            edit_instruction = result[5:].strip()
            _write_approval_state(approvals_path, script_text, status="edit_requested",
                                  edit_instructions=edit_instruction)
            logger.info(f"ScriptApproverTool: Edit requested: {edit_instruction}")
            return f"EDIT: {edit_instruction}"
        else:
            _write_approval_state(approvals_path, script_text, status="approved")
            logger.info("ScriptApproverTool: Script approved by user.")
            return "APPROVED"


def _print_script(script_text: str) -> None:
    """Pretty-print the script to the console."""
    width = 70
    print("\n" + "=" * width)
    print("  SCRIPT PREVIEW")
    print("=" * width)
    # Wrap long lines for readability
    for line in script_text.splitlines():
        if line.strip() == "":
            print()
        else:
            wrapped = textwrap.fill(line, width=width - 4, initial_indent="  ",
                                    subsequent_indent="    ")
            print(wrapped)
    print("=" * width)


def _write_approval_state(
    approvals_path: str,
    script_text: str,
    status: str,
    edit_instructions: str = "",
) -> None:
    """Write the approval state atomically to the approvals JSON file."""
    os.makedirs(os.path.dirname(approvals_path), exist_ok=True)
    state = {
        "timestamp": time.time(),
        "status": status,
        "script_preview": script_text[:2000],  # truncate for JSON size
        "edit_instructions": edit_instructions,
    }
    tmp_path = approvals_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_path, approvals_path)
    except Exception as e:
        logger.warning(f"Could not write approvals.json: {e}")


def _wait_for_response(timeout_seconds: int = 300) -> str:
    """
    Wait for the user to type APPROVE or EDIT: <instructions>.
    Also polls the approvals.json file for dashboard-driven responses.
    Returns the user response string.
    """
    import select

    deadline = time.time() + timeout_seconds

    try:
        from config import get_config
        approvals_path = get_config().approvals_path
    except Exception:
        approvals_path = os.path.join(BASE_DIR, "output", "approvals.json")

    while time.time() < deadline:
        remaining = deadline - time.time()

        # Check for dashboard-driven approval
        dashboard_response = _check_dashboard_approval(approvals_path)
        if dashboard_response:
            return dashboard_response

        # Check stdin (non-blocking on Unix)
        if sys.platform != "win32":
            ready, _, _ = select.select([sys.stdin], [], [], min(remaining, 1.0))
            if ready:
                line = sys.stdin.readline().strip()
                upper = line.upper()
                if upper == "APPROVE":
                    return "APPROVE"
                elif upper.startswith("EDIT:"):
                    return line  # preserve original case for instructions
                else:
                    print("  (Type APPROVE or EDIT: <instructions>)\n  > ", end="", flush=True)
        else:
            time.sleep(0.5)

    print("\n  Timeout — auto-approving.")
    return "APPROVE"


def _check_dashboard_approval(approvals_path: str) -> str:
    """Check if dashboard has written an approval decision."""
    if not os.path.exists(approvals_path):
        return ""
    try:
        with open(approvals_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        status = state.get("status", "")
        if status == "dashboard_approved":
            return "APPROVE"
        elif status == "dashboard_rejected":
            return "EDIT: User rejected via dashboard — please revise the script."
        elif status == "dashboard_edit":
            instructions = state.get("edit_instructions", "Please improve the script.")
            return f"EDIT: {instructions}"
    except Exception:
        pass
    return ""
