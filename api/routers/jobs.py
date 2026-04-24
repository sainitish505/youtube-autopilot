"""
api/routers/jobs.py — CRUD for video generation jobs.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from api.models.db import get_db, Job, JobAgentStatus, JobAsset
from api.models.schemas import CreateJobRequest, JobOut, JobListOut, AgentStatusOut
from api.dependencies import get_current_user, CurrentUser
from api.services.job_queue import enqueue_pipeline

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

AGENT_ORDER = ["CEO", "ScriptPolisher", "VisualGenerator", "AudioEngineer", "VideoEditor", "SEOOptimizer", "Uploader"]


@router.post("", response_model=dict)
async def create_job(
    req: CreateJobRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Queue a new video generation job for the current user."""
    job_id = uuid.uuid4()

    # Create job record
    job = Job(
        id=job_id,
        user_id=uuid.UUID(user.id),
        status="queued",
        niche=req.niche or "",
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)

    # Create per-agent status rows
    for agent in AGENT_ORDER:
        db.add(JobAgentStatus(job_id=job_id, agent_name=agent, status="pending"))

    await db.commit()

    # Enqueue background task
    await enqueue_pipeline(user_id=user.id, job_id=str(job_id))

    return {"job_id": str(job_id), "status": "queued"}


@router.get("", response_model=JobListOut)
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """List all jobs for the current user, newest first."""
    result = await db.execute(
        select(Job)
        .where(Job.user_id == uuid.UUID(user.id))
        .order_by(Job.created_at.desc())
        .limit(50)
    )
    jobs = result.scalars().all()
    return JobListOut(jobs=[_job_to_out(j) for j in jobs], total=len(jobs))


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get full job details including agent statuses and assets."""
    result = await db.execute(
        select(Job).where(Job.id == uuid.UUID(job_id), Job.user_id == uuid.UUID(user.id))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    agents_result = await db.execute(
        select(JobAgentStatus).where(JobAgentStatus.job_id == uuid.UUID(job_id))
    )
    agents = agents_result.scalars().all()

    assets_result = await db.execute(
        select(JobAsset).where(JobAsset.job_id == uuid.UUID(job_id))
    )
    assets = assets_result.scalars().all()

    out = _job_to_out(job)
    out.agents = [AgentStatusOut(agent_name=a.agent_name, status=a.status, updated_at=a.updated_at) for a in agents]
    out.assets = [{"type": a.type, "url": a.public_url, "path": a.r2_path} for a in assets]
    return out


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Cancel a queued or running job."""
    await db.execute(
        update(Job)
        .where(Job.id == uuid.UUID(job_id), Job.user_id == uuid.UUID(user.id))
        .values(status="cancelled")
    )
    await db.commit()
    return {"message": "Job cancelled"}


def _job_to_out(job: Job) -> JobOut:
    return JobOut(
        id=str(job.id),
        status=job.status,
        niche=job.niche,
        title=job.title,
        scenes_count=job.scenes_count,
        video_url=job.video_url,
        total_cost_usd=job.total_cost_usd or 0.0,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )
