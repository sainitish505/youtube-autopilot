"""
api/routers/analytics.py — Per-user usage analytics and cost tracking.
"""
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone
from api.models.db import get_db, Job, AnalyticsEvent
from api.models.schemas import AnalyticsSummaryOut
from api.dependencies import get_current_user, CurrentUser

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummaryOut)
async def get_analytics_summary(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Return per-user analytics summary."""
    uid = uuid.UUID(user.id)
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Total jobs
    total_res = await db.execute(select(func.count(Job.id)).where(Job.user_id == uid))
    total_videos = total_res.scalar() or 0

    # Total cost
    cost_res = await db.execute(select(func.sum(Job.total_cost_usd)).where(Job.user_id == uid))
    total_cost = float(cost_res.scalar() or 0.0)

    # Success rate
    done_res = await db.execute(
        select(func.count(Job.id)).where(Job.user_id == uid, Job.status == "completed")
    )
    done = done_res.scalar() or 0
    success_rate = (done / total_videos * 100) if total_videos > 0 else 0.0

    # This month
    month_res = await db.execute(
        select(func.count(Job.id)).where(Job.user_id == uid, Job.created_at >= month_start)
    )
    videos_this_month = month_res.scalar() or 0

    month_cost_res = await db.execute(
        select(func.sum(Job.total_cost_usd)).where(Job.user_id == uid, Job.created_at >= month_start)
    )
    cost_this_month = float(month_cost_res.scalar() or 0.0)

    # Cost by type
    cost_by_type_res = await db.execute(
        select(AnalyticsEvent.event_type, func.sum(AnalyticsEvent.cost_usd))
        .where(AnalyticsEvent.user_id == uid)
        .group_by(AnalyticsEvent.event_type)
    )
    cost_by_type = {row[0]: float(row[1]) for row in cost_by_type_res.all()}

    # Videos by niche
    niche_res = await db.execute(
        select(Job.niche, func.count(Job.id))
        .where(Job.user_id == uid, Job.niche.isnot(None))
        .group_by(Job.niche)
        .order_by(func.count(Job.id).desc())
        .limit(10)
    )
    videos_by_niche = {row[0]: row[1] for row in niche_res.all() if row[0]}

    return AnalyticsSummaryOut(
        total_videos=total_videos,
        total_cost_usd=total_cost,
        success_rate=success_rate,
        avg_cost_per_video=total_cost / done if done > 0 else 0.0,
        videos_this_month=videos_this_month,
        cost_this_month_usd=cost_this_month,
        cost_by_type=cost_by_type,
        videos_by_niche=videos_by_niche,
    )


@router.get("/events")
async def get_events(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Return recent analytics events for the current user."""
    uid = uuid.UUID(user.id)
    result = await db.execute(
        select(AnalyticsEvent)
        .where(AnalyticsEvent.user_id == uid)
        .order_by(AnalyticsEvent.created_at.desc())
        .limit(100)
    )
    events = result.scalars().all()
    return {"events": [
        {"type": e.event_type, "cost_usd": e.cost_usd, "tokens": e.tokens_used, "ts": e.created_at}
        for e in events
    ]}
