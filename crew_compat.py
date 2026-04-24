"""
crew_compat.py — Bridge between UserContext and the existing crew.py pipeline.

Patches the config singleton temporarily for each user's pipeline run,
then calls run_ceo_crew(). In a future refactor, crew.py would accept
UserContext directly.
"""
from __future__ import annotations
import os
import sys
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def run_pipeline_with_context(ctx, update_agent_status_fn: Optional[Callable] = None) -> dict:
    """
    Run the full CEO + production pipeline with per-user context.

    Temporarily patches the config singleton with user-specific values
    so the existing pipeline code works without modification.

    Returns dict with youtube_url, title, scenes_count, total_cost_usd.
    """
    import config as cfg_module

    # ── Patch the config singleton ────────────────────────────────────────────
    from config import Config
    patched = Config(
        openai_api_key=ctx.openai_api_key,
        gemini_api_key="",
        autonomous_mode=ctx.autonomous_mode,
        max_video_minutes=ctx.max_video_minutes,
        default_niche=ctx.default_niche,
        human_approval_timeout=300,
        video_model=ctx.video_model,
        tts_voice=ctx.tts_voice,
        upload_privacy=ctx.upload_privacy,
        auto_approve_under_dollars=ctx.auto_approve_under_dollars,
        video_resolution="1920x1080",
        short_resolution="720x1280",
        crossfade_duration=ctx.crossfade_duration,
        background_music_volume=ctx.background_music_volume,
        log_level=ctx.log_level,
        output_dir=ctx.output_dir,
        logs_dir=os.path.join(ctx.output_dir, "logs"),
        youtube_refresh_token=ctx.youtube_refresh_token or "",
    )
    # Note: approvals_path and dashboard_state_path are init=False fields
    # computed by Config.__post_init__ from output_dir — do NOT pass them here.

    # Temporarily inject the patched config
    original = cfg_module._config_instance
    cfg_module._config_instance = patched

    # Also set OPENAI_API_KEY env var for tools that read it directly
    original_env_key = os.environ.get("OPENAI_API_KEY", "")
    os.environ["OPENAI_API_KEY"] = ctx.openai_api_key

    result = {"youtube_url": "", "title": "", "scenes_count": 0, "total_cost_usd": 0.0}
    try:
        from crew import run_ceo_crew
        youtube_url = run_ceo_crew(patched)
        result["youtube_url"] = youtube_url or ""
        logger.info(f"Pipeline completed: {youtube_url}")
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        raise
    finally:
        # Restore original config
        cfg_module._config_instance = original
        os.environ["OPENAI_API_KEY"] = original_env_key

    return result
