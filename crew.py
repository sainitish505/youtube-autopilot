"""
crew.py — CEO Crew definition and entry point for the full pipeline.

Architecture:
  CEO Agent (GPT-4o)
    └─ Task: Research niche → design video → write script → get approval → produce cost estimate
    └─ Output: VideoPlan (Pydantic)

  On approval: CrewFactory.build_and_run(plan) executes the production sub-crews.

The `run_ceo_crew(cfg)` function is called from main.py.
"""

import json
import logging
import os
import sys
import time
from typing import List, Optional

from crewai import Agent, Crew, LLM, Process, Task
from pydantic import BaseModel, Field

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

logger = logging.getLogger(__name__)


# ── Pydantic output model for the CEO Task ────────────────────────────────────

class SceneSpec(BaseModel):
    scene_num: int = Field(description="1-based scene number")
    description: str = Field(description="Visual description of what happens in this scene")
    duration_seconds: int = Field(description="Scene duration in seconds (typically 5-15s)")
    voiceover_text: str = Field(description="Voiceover narration text for this scene")


class VideoPlan(BaseModel):
    niche: str = Field(description="Video niche/topic category")
    title: str = Field(description="YouTube video title (under 60 chars)")
    script: str = Field(description="Full script overview / narrative arc")
    scenes: List[SceneSpec] = Field(description="Scene-by-scene breakdown")
    video_length_minutes: float = Field(description="Total estimated video length in minutes")
    target_audience: str = Field(description="Specific target audience description")
    tags: List[str] = Field(description="15-20 YouTube SEO tags")
    thumbnail_description: str = Field(description="Visual concept for the thumbnail")
    seo_description: str = Field(description="YouTube description (150-300 words)")
    approved: bool = Field(default=False, description="Whether the plan was approved")
    approval_message: str = Field(default="", description="Approval or edit message")


# ── CEO Task description ──────────────────────────────────────────────────────

def _build_ceo_task_description(niche_hint: str, max_minutes: int) -> str:
    niche_instruction = (
        f"Focus on this niche: '{niche_hint}'."
        if niche_hint
        else "Explore diverse trending niches RIGHT NOW: finance, lifestyle, science, sports, food, "
             "history, comedy, travel, technology, education, health, gaming, DIY, personal development, "
             "true crime, motivation, art, nature, fitness, or any other category where you see genuine "
             "viral potential. Do NOT default to AI unless AI content is genuinely the #1 trending topic. "
             "Prioritize niche diversity and fresh perspectives."
    )
    return f"""
You are the CEO of a YouTube channel. Your mission: produce a high-performing video.

STEP 1 — RESEARCH
Use the Trend Research Tool to identify trending topics.
{niche_instruction}
After getting the ranked ideas: If #1 is AI-focused (contains keywords like "AI", "artificial intelligence", "machine learning", "ChatGPT", "Sora", etc.), SKIP IT and select #2 or #3 instead to ensure niche diversity.
Only select the #1 AI-focused idea if alternatives are also AI-focused or if AI is truly the only viable trending topic.

STEP 2 — PLAN
Design the video concept:
- Target audience (specific, not just "everyone")
- Content format (educational / story / listicle / how-to / etc.)
- Hook strategy (first 3 seconds must stop the scroll)
- Video length: between 3 and {max_minutes} minutes

STEP 3 — SCRIPT
Write a full scene-by-scene script.
- Each scene: 5-15 seconds
- Total scenes: enough to fill {max_minutes} minutes (target 8-12 for a 5-10 min video)
- Each scene must have: description (what's shown), duration_seconds, voiceover_text
- Voiceover must be conversational, punchy, and match scene duration
  (approx 150 words per minute = ~1 word per 0.4 seconds)

STEP 4 — COST ESTIMATE
Use the Cost Estimator Tool with the plan JSON to get a cost breakdown.
The plan JSON must include all scenes with voiceover_text.

STEP 5 — APPROVAL
Use the Script Approver Tool to present the script and get approval.
If the tool returns "EDIT: <instructions>", revise the script accordingly and re-submit.
Only proceed once you get "APPROVED".

STEP 6 — OUTPUT
Return a complete VideoPlan JSON with all scenes, metadata, and approved=True.

IMPORTANT: Be specific. Vague descriptions make bad videos.
"""


def _build_ceo_task_expected_output() -> str:
    return (
        "A complete VideoPlan JSON object with: niche, title, script, "
        "scenes (list of {scene_num, description, duration_seconds, voiceover_text}), "
        "video_length_minutes, target_audience, tags (15-20 items), "
        "thumbnail_description, seo_description, approved=true, approval_message."
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def run_ceo_crew(cfg) -> str:
    """
    Run the full CEO orchestration pipeline.

    Parameters
    ----------
    cfg : Config
        Loaded configuration object from config.py.

    Returns
    -------
    str
        YouTube URL of the published video.
    """
    from agents.ceo_agent import build_ceo_agent
    from agents.crew_factory import CrewFactory
    from tools.dashboard_tool import update_status, set_pipeline_failed, _load_state, _save_state, _get_state_path

    # Initialise dashboard state
    state_path = _get_state_path()
    from tools.dashboard_tool import _default_state
    initial_state = _default_state()
    initial_state["agents"] = {
        "CEO": {"status": "running", "updated_at": time.time()},
        "ScriptPolisher": {"status": "pending", "updated_at": time.time()},
        "VisualGenerator": {"status": "pending", "updated_at": time.time()},
        "AudioEngineer": {"status": "pending", "updated_at": time.time()},
        "VideoEditor": {"status": "pending", "updated_at": time.time()},
        "SEOOptimizer": {"status": "pending", "updated_at": time.time()},
        "Uploader": {"status": "pending", "updated_at": time.time()},
    }
    from tools.dashboard_tool import _save_state
    _save_state(state_path, initial_state)

    # Build CEO agent
    ceo_agent = build_ceo_agent(cfg.openai_api_key)

    # Build CEO task
    ceo_task = Task(
        description=_build_ceo_task_description(cfg.default_niche, cfg.max_video_minutes),
        expected_output=_build_ceo_task_expected_output(),
        agent=ceo_agent,
        output_pydantic=VideoPlan,
    )

    # Run CEO crew (single-agent with hierarchical planning)
    logger.info("Starting CEO crew...")
    ceo_crew = Crew(
        agents=[ceo_agent],
        tasks=[ceo_task],
        process=Process.sequential,
        verbose=True,
        memory=False,
    )

    try:
        result = ceo_crew.kickoff(inputs={
            "niche": cfg.default_niche or "",
            "max_minutes": cfg.max_video_minutes,
        })
    except Exception as e:
        logger.exception(f"CEO crew failed: {e}")
        update_status("CEO", "failed")
        set_pipeline_failed(str(e))
        raise

    # ── Parse the plan ────────────────────────────────────────────────────────
    plan = _parse_ceo_output(result)

    if not plan:
        msg = "CEO crew did not return a valid production plan."
        logger.error(msg)
        update_status("CEO", "failed")
        set_pipeline_failed(msg)
        raise RuntimeError(msg)

    if not plan.get("approved", False):
        msg = f"Plan was not approved. Message: {plan.get('approval_message', 'none')}"
        logger.warning(msg)
        update_status("CEO", "failed")
        set_pipeline_failed(msg)
        raise RuntimeError(msg)

    update_status("CEO", "done")
    logger.info(f"CEO plan approved: '{plan.get('title')}' — {len(plan.get('scenes', []))} scenes")

    # ── Hand off to CrewFactory ───────────────────────────────────────────────
    factory = CrewFactory(
        openai_api_key=cfg.openai_api_key,
        youtube_refresh_token=getattr(cfg, "youtube_refresh_token", ""),
    )
    youtube_url = factory.build_and_run(plan)

    return youtube_url


def _parse_ceo_output(result) -> Optional[dict]:
    """
    Extract the plan dict from the CEO crew result.
    Handles: Pydantic model, raw dict, JSON string, or string with embedded JSON.
    """
    if result is None:
        return None

    # Pydantic model (ideal path)
    if isinstance(result, VideoPlan):
        return result.model_dump()

    # CrewAI TaskOutput wraps the pydantic model
    if hasattr(result, "pydantic") and result.pydantic is not None:
        obj = result.pydantic
        if isinstance(obj, VideoPlan):
            return obj.model_dump()
        if isinstance(obj, dict):
            return obj

    # Raw output string
    raw = None
    if hasattr(result, "raw"):
        raw = result.raw
    elif hasattr(result, "output"):
        raw = result.output
    elif isinstance(result, str):
        raw = result

    if raw:
        # Try direct JSON parse
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "scenes" in data:
                return data
        except json.JSONDecodeError:
            pass

        # Try extracting JSON block from prose
        import re
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                if isinstance(data, dict) and "scenes" in data:
                    return data
            except json.JSONDecodeError:
                pass

    logger.error(f"Could not parse CEO output. Type={type(result)}, raw={str(result)[:300]}")
    return None
