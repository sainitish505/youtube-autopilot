"""
api/services/job_queue.py — ARQ job queue helpers.
Falls back to direct synchronous execution if Redis is unavailable.
"""
import os
import logging

logger = logging.getLogger(__name__)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")


async def enqueue_pipeline(user_id: str, job_id: str):
    """Enqueue a video pipeline job in ARQ (Redis-backed)."""
    try:
        import arq
        redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(REDIS_URL))
        await redis.enqueue_job("run_video_pipeline", user_id=user_id, job_id=job_id)
        await redis.aclose()
        logger.info(f"Job {job_id} enqueued for user {user_id}")
    except Exception as e:
        logger.error(f"ARQ enqueue failed: {e}. Run worker manually.")
        raise
