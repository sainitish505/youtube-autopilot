"""
tools/cost_estimator.py — CostEstimatorTool

Accepts a JSON production plan and returns a detailed cost breakdown.
If the total exceeds auto_approve_under_dollars from config, prompts the
user for APPROVE/REJECT via stdin (unless autonomous_mode is True).
"""

import json
import logging
import os
import sys
import time
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
logger = logging.getLogger(__name__)

# ── Cost rates (as of 2025) ────────────────────────────────────────────────────
RATES = {
    "gpt4o_per_1k_tokens": 0.005,       # input+output blended
    "gpt4o_mini_per_1k_tokens": 0.00015,
    "sora2_per_8s_clip": 0.30,
    "tts_per_1k_chars": 0.015,
    "dalle3_per_image": 0.04,
    "youtube_upload": 0.00,
}

# Tokens per agent call estimate
TOKENS_PER_AGENT_CALL = 2000


class CostEstimatorInput(BaseModel):
    plan_json: str = Field(
        description=(
            "JSON string containing the production plan with keys: "
            "scenes (list of scene dicts), tags (list), title, "
            "video_length_minutes (int/float). "
            "Each scene must have: duration_seconds, voiceover_text."
        )
    )


class CostEstimatorTool(BaseTool):
    name: str = "Cost Estimator"
    description: str = (
        "Calculates the estimated cost of producing a YouTube video from a production plan. "
        "Input: a JSON string containing the plan (scenes, durations, voiceover text, etc). "
        "Returns a cost breakdown string and raises a prompt for human approval if needed."
    )
    args_schema: Type[BaseModel] = CostEstimatorInput

    def _run(self, plan_json: str) -> str:
        try:
            plan = json.loads(plan_json)
        except json.JSONDecodeError as e:
            return f"ERROR: Invalid JSON input to CostEstimatorTool: {e}"

        try:
            return self._estimate(plan)
        except Exception as e:
            logger.exception(f"CostEstimatorTool failed: {e}")
            return f"ERROR: Cost estimation failed: {e}"

    def _estimate(self, plan: dict) -> str:
        scenes = plan.get("scenes", [])
        num_scenes = len(scenes)
        if num_scenes == 0:
            return "ERROR: Plan contains no scenes — cannot estimate cost."

        # ── LLM costs ─────────────────────────────────────────────────────────
        # CEO: 1 call × 2K tokens (GPT-4o)
        ceo_tokens = TOKENS_PER_AGENT_CALL
        ceo_cost = (ceo_tokens / 1000) * RATES["gpt4o_per_1k_tokens"]

        # Sub-agents: 5 agents (ScriptPolisher, VisualGenerator, AudioEngineer,
        #             VideoEditor, SEOOptimizer, UploaderAgent) = 6 calls × mini
        num_sub_agents = 6
        sub_tokens = TOKENS_PER_AGENT_CALL * num_sub_agents
        sub_cost = (sub_tokens / 1000) * RATES["gpt4o_mini_per_1k_tokens"]

        llm_cost = ceo_cost + sub_cost

        # ── Sora video generation ──────────────────────────────────────────────
        # Each scene generates one 8-second Sora clip
        sora_cost = num_scenes * RATES["sora2_per_8s_clip"]

        # ── TTS (voiceover) ────────────────────────────────────────────────────
        total_chars = sum(
            len(scene.get("voiceover_text", "")) for scene in scenes
        )
        tts_cost = (total_chars / 1000) * RATES["tts_per_1k_chars"]

        # ── Thumbnail (DALL-E 3 × 1) ───────────────────────────────────────────
        thumbnail_cost = RATES["dalle3_per_image"]

        # ── Upload ────────────────────────────────────────────────────────────
        upload_cost = RATES["youtube_upload"]

        # ── Total ─────────────────────────────────────────────────────────────
        total = llm_cost + sora_cost + tts_cost + thumbnail_cost + upload_cost

        lines = [
            "=" * 58,
            "  PRODUCTION COST ESTIMATE",
            "=" * 58,
            f"  Title         : {plan.get('title', '(untitled)')}",
            f"  Scenes        : {num_scenes}",
            f"  Voiceover     : {total_chars:,} chars",
            "-" * 58,
            f"  GPT-4o (CEO)  : ${ceo_cost:.4f}  ({ceo_tokens:,} tokens)",
            f"  GPT-4o-mini   : ${sub_cost:.4f}  ({sub_tokens:,} tokens, {num_sub_agents} agents)",
            f"  Sora-2 clips  : ${sora_cost:.4f}  ({num_scenes} clips × $0.30)",
            f"  OpenAI TTS    : ${tts_cost:.4f}  ({total_chars:,} chars)",
            f"  DALL-E 3 thumb: ${thumbnail_cost:.4f}",
            f"  YouTube upload: $0.0000  (free)",
            "-" * 58,
            f"  TOTAL ESTIMATE: ${total:.4f}",
            "=" * 58,
        ]
        breakdown_str = "\n".join(lines)
        print(breakdown_str)

        # ── Approval logic ─────────────────────────────────────────────────────
        try:
            from config import get_config
            cfg = get_config()
            autonomous = cfg.autonomous_mode
            threshold = cfg.auto_approve_under_dollars
            timeout = cfg.human_approval_timeout
        except Exception:
            autonomous = True
            threshold = 2.0
            timeout = 300

        if autonomous or total <= threshold:
            status = "AUTO-APPROVED"
            print(f"\n  [{status}] Cost ${total:.4f} within threshold ${threshold:.2f}\n")
            return breakdown_str + f"\n\nSTATUS: {status} — total ${total:.4f}"

        # Human approval required
        print(f"\n  Cost ${total:.4f} exceeds threshold ${threshold:.2f}.")
        print("  Type APPROVE to continue, or REJECT to abort:")
        print(f"  (Auto-approving in {timeout}s if no input)\n")

        approved = _wait_for_approval(timeout_seconds=timeout)
        if approved:
            return breakdown_str + f"\n\nSTATUS: HUMAN APPROVED — total ${total:.4f}"
        else:
            return breakdown_str + f"\n\nSTATUS: REJECTED — Pipeline aborted by user."


def _wait_for_approval(timeout_seconds: int = 300) -> bool:
    """
    Wait up to timeout_seconds for the user to type APPROVE or REJECT.
    Returns True if approved (or timed out), False if explicitly rejected.
    """
    import select

    deadline = time.time() + timeout_seconds
    print("  > ", end="", flush=True)

    while time.time() < deadline:
        remaining = deadline - time.time()
        # Use select on stdin to avoid blocking forever (Unix only)
        if sys.platform != "win32":
            ready, _, _ = select.select([sys.stdin], [], [], min(remaining, 1.0))
            if ready:
                line = sys.stdin.readline().strip().upper()
                if line == "APPROVE":
                    print("  Approved by user.")
                    return True
                elif line == "REJECT":
                    print("  Rejected by user.")
                    return False
        else:
            # Windows: simple blocking with a short sleep
            try:
                import msvcrt
                if msvcrt.kbhit():
                    line = input().strip().upper()
                    if line == "APPROVE":
                        return True
                    elif line == "REJECT":
                        return False
            except Exception:
                pass
            time.sleep(0.5)

    print("  Timeout reached — auto-approving.")
    return True
