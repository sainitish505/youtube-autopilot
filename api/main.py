"""
api/main.py — FastAPI application entry point.
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (two levels up from api/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path, override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import auth, jobs, api_keys, analytics, youtube_oauth, settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="YouTube Autopilot API",
    description="Multi-tenant SaaS API for AI-powered YouTube video generation",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow Streamlit frontend and any configured origins
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:8501,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(api_keys.router)
app.include_router(analytics.router)
app.include_router(youtube_oauth.router)
app.include_router(settings.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "youtube-autopilot-api", "version": "2.0.0"}


@app.get("/")
async def root():
    return {
        "message": "YouTube Autopilot Agent v2 API",
        "docs": "/docs",
        "health": "/health",
    }
