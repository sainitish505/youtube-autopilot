"""
api/models/db.py — SQLAlchemy async models + Supabase connection.

Tables: user_profiles, user_api_keys, user_settings, jobs,
        job_agent_statuses, job_assets, analytics_events
"""
import os
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, String, Boolean, Integer, Float, Text,
    TIMESTAMP, LargeBinary, ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import uuid

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/youtube_saas"
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


class UserProfile(Base):
    __tablename__ = "user_profiles"
    id = Column(UUID(as_uuid=True), primary_key=True)
    display_name = Column(String(255))
    plan = Column(String(50), default="free")
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)


class UserApiKeys(Base):
    __tablename__ = "user_api_keys"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False, unique=True)
    openai_api_key_enc = Column(LargeBinary)
    youtube_refresh_token_enc = Column(LargeBinary)
    youtube_channel_id = Column(String(255))
    youtube_channel_name = Column(String(255))
    youtube_connected_at = Column(TIMESTAMP(timezone=True))
    openai_added_at = Column(TIMESTAMP(timezone=True))
    updated_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)


class UserSettings(Base):
    __tablename__ = "user_settings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False, unique=True)
    autonomous_mode = Column(Boolean, default=True)
    max_video_minutes = Column(Integer, default=10)
    default_niche = Column(String(255), default="")
    tts_voice = Column(String(50), default="alloy")
    upload_privacy = Column(String(50), default="public")
    video_model = Column(String(50), default="sora-2")
    auto_approve_under_dollars = Column(Float, default=2.0)


class Job(Base):
    __tablename__ = "jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), default="queued")
    niche = Column(String(255))
    title = Column(String(255))
    scenes_count = Column(Integer)
    video_url = Column(Text)
    r2_video_path = Column(Text)
    total_cost_usd = Column(Float, default=0.0)
    error_message = Column(Text)
    plan_json = Column(JSONB)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    started_at = Column(TIMESTAMP(timezone=True))
    completed_at = Column(TIMESTAMP(timezone=True))


class JobAgentStatus(Base):
    __tablename__ = "job_agent_statuses"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    agent_name = Column(String(100), nullable=False)
    status = Column(String(50), default="pending")
    updated_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("job_id", "agent_name"),)


class JobAsset(Base):
    __tablename__ = "job_assets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False)
    r2_path = Column(Text, nullable=False)
    public_url = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True)
    event_type = Column(String(100), nullable=False)
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
