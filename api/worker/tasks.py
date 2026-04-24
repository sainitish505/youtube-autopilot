"""
api/worker/tasks.py — ARQ background worker tasks.

Each task runs a full CrewAI video pipeline for one user job.
Executed by: python -m arq api.worker.WorkerSettings
"""
import os
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

# Make sure parent package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

logger = logging.getLogger(__name__)


async def run_video_pipeline(ctx: dict, user_id: str, job_id: str):
    """
    Main ARQ task: runs the full CrewAI pipeline for one user job.

    Steps:
      1. Load user's API keys from DB (decrypt)
      2. Build UserContext with isolated output dir
      3. Run CEO crew -> get video plan
      4. Run production sub-crews (Sora, TTS, MoviePy, YouTube)
      5. Upload artifacts to R2
      6. Update job record as completed
    """
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select, update
    from api.models.db import AsyncSessionLocal, Job, UserApiKeys, UserSettings, JobAgentStatus, JobAsset, AnalyticsEvent
    from api.services.encryption import decrypt_key
    from api.services.storage import upload_job_outputs
    from core.user_context import UserContext
    import uuid

    logger.info(f"[Worker] Starting pipeline: job={job_id} user={user_id}")

    async with AsyncSessionLocal() as db:
        # ── 1. Load user data ─────────────────────────────────────────────────
        uid = uuid.UUID(user_id)
        jid = uuid.UUID(job_id)

        keys_res = await db.execute(select(UserApiKeys).where(UserApiKeys.user_id == uid))
        keys = keys_res.scalar_one_or_none()

        settings_res = await db.execute(select(UserSettings).where(UserSettings.user_id == uid))
        settings = settings_res.scalar_one_or_none()

        if not keys or not keys.openai_api_key_enc:
            await db.execute(
                update(Job).where(Job.id == jid).values(
                    status="failed",
                    error_message="No OpenAI API key configured. Please add it in Settings.",
                    completed_at=_now()
                )
            )
            await db.commit()
            return

        # ── 2. Build UserContext ──────────────────────────────────────────────
        openai_key = decrypt_key(keys.openai_api_key_enc)
        yt_token = decrypt_key(keys.youtube_refresh_token_enc) if keys.youtube_refresh_token_enc else None

        ctx_settings = {
            "autonomous_mode": getattr(settings, "autonomous_mode", True) if settings else True,
            "max_video_minutes": getattr(settings, "max_video_minutes", 10) if settings else 10,
            "default_niche": getattr(settings, "default_niche", "") if settings else "",
            "tts_voice": getattr(settings, "tts_voice", "alloy") if settings else "alloy",
            "upload_privacy": getattr(settings, "upload_privacy", "public") if settings else "public",
            "video_model": getattr(settings, "video_model", "sora-2") if settings else "sora-2",
            "auto_approve_under_dollars": getattr(settings, "auto_approve_under_dollars", 2.0) if settings else 2.0,
        }

        # Get the niche from the job record
        job_res = await db.execute(select(Job).where(Job.id == jid))
        job = job_res.scalar_one_or_none()
        if job and job.niche:
            ctx_settings["default_niche"] = job.niche

        user_ctx = UserContext(
            user_id=user_id,
            job_id=job_id,
            openai_api_key=openai_key,
            youtube_refresh_token=yt_token,
            youtube_channel_id=keys.youtube_channel_id,
        )
        user_ctx.autonomous_mode = ctx_settings["autonomous_mode"]
        user_ctx.max_video_minutes = ctx_settings["max_video_minutes"]
        user_ctx.default_niche = ctx_settings["default_niche"]
        user_ctx.tts_voice = ctx_settings["tts_voice"]
        user_ctx.upload_privacy = ctx_settings["upload_privacy"]
        user_ctx.video_model = ctx_settings["video_model"]
        user_ctx.auto_approve_under_dollars = ctx_settings["auto_approve_under_dollars"]
        user_ctx.ensure_dirs()

        # ── 3. Mark job as running ────────────────────────────────────────────
        await db.execute(
            update(Job).where(Job.id == jid).values(status="running", started_at=_now())
        )
        await db.commit()

        # ── 4. Run pipeline ───────────────────────────────────────────────────
        try:
            # Run CEO crew with user context
            from crew_compat import run_pipeline_with_context
            result = run_pipeline_with_context(user_ctx, update_agent_status_fn=None)

            youtube_url = result.get("youtube_url", "")
            title = result.get("title", "")
            scenes_count = result.get("scenes_count", 0)
            total_cost = result.get("total_cost_usd", 0.0)

        except Exception as e:
            logger.exception(f"[Worker] Pipeline failed for job {job_id}: {e}")
            await db.execute(
                update(Job).where(Job.id == jid).values(
                    status="failed",
                    error_message=str(e),
                    completed_at=_now()
                )
            )
            await db.commit()
            return

        # ── 5. Upload artifacts to R2 ─────────────────────────────────────────
        try:
            urls = upload_job_outputs(user_id, job_id, user_ctx.output_dir)
            for rel_path, url in urls.items():
                ftype = "video_clip" if rel_path.endswith(".mp4") else \
                        "audio" if rel_path.endswith(".mp3") else \
                        "thumbnail" if "thumbnail" in rel_path else "image"
                db.add(JobAsset(job_id=jid, type=ftype, r2_path=f"{user_id}/{job_id}/{rel_path}", public_url=url))
            await db.commit()
        except Exception as e:
            logger.warning(f"[Worker] R2 upload failed (non-fatal): {e}")

        # ── 6. Mark completed ─────────────────────────────────────────────────
        await db.execute(
            update(Job).where(Job.id == jid).values(
                status="completed",
                video_url=youtube_url,
                title=title,
                scenes_count=scenes_count,
                total_cost_usd=total_cost,
                completed_at=_now()
            )
        )
        await db.commit()
        logger.info(f"[Worker] Job {job_id} completed. URL: {youtube_url}")


def _build_redis_settings():
    import arq.connections
    return arq.connections.RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://localhost:6379")
    )


class WorkerSettings:
    """ARQ worker configuration. redis_settings must be a class-level attribute."""
    functions = [run_video_pipeline]
    redis_settings = _build_redis_settings()
    # Keep queue_read_limit and job_timeout sensible for long-running pipelines
    queue_read_limit = 4
    job_timeout = 3600      # 60 min max per job
    keep_result = 3600      # keep results for 1 hour
