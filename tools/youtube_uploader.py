"""
tools/youtube_uploader.py — YouTubeUploaderTool

Uploads the final video to YouTube via the Data API v3.

Authentication modes (tried in order):
  1. Per-user OAuth refresh token (multi-tenant SaaS mode)
     Passed via config.youtube_refresh_token or the YOUTUBE_REFRESH_TOKEN env var.
  2. token.pickle file (legacy single-user CLI mode)
  3. InstalledAppFlow browser consent (first-time CLI setup only)

The privacy setting is read from config (public | unlisted | private).
"""

import logging
import os
import pickle
from pathlib import Path
from typing import List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubeUploaderInput(BaseModel):
    video_path: str = Field(description="Absolute path to the final MP4 video file.")
    title: str = Field(description="YouTube video title (under 100 chars).")
    description: str = Field(description="YouTube video description (150-300 words recommended).")
    tags: List[str] = Field(default_factory=list, description="List of YouTube SEO tags.")
    category_id: str = Field(default="28", description="YouTube category ID string (default: 28 = Science & Technology).")


class YouTubeUploaderTool(BaseTool):
    name: str = "YouTube Video Uploader"
    description: str = (
        "Uploads a video file to YouTube. "
        "Input: video_path (absolute path to MP4), title, description, tags (list), "
        "optional category_id. Returns the YouTube video URL."
    )
    args_schema: Type[BaseModel] = YouTubeUploaderInput

    def _run(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: List[str],
        category_id: str = "28",
    ) -> str:
        """Upload video and return YouTube URL."""
        if not os.path.exists(video_path):
            return f"ERROR: Video file not found: {video_path}"

        try:
            creds = self._get_credentials()
        except Exception as e:
            logger.error(f"YouTube auth failed: {e}")
            return f"ERROR: YouTube authentication failed — {e}"

        if creds is None:
            return "ERROR: No YouTube credentials available. Connect YouTube in Settings."

        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            youtube = build("youtube", "v3", credentials=creds)

            # Read privacy from config
            try:
                from config import get_config
                privacy = get_config().upload_privacy
            except Exception:
                privacy = os.environ.get("UPLOAD_PRIVACY", "public")

            # Sanitise tags
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            body = {
                "snippet": {
                    "title": title[:100],
                    "description": description + "\n\n#AIGenerated #YouTubeAutopilot",
                    "tags": tags[:30],        # YouTube allows max 500 chars total
                    "categoryId": str(category_id),
                },
                "status": {
                    "privacyStatus": privacy,
                    "selfDeclaredMadeForKids": False,
                },
            }

            media = MediaFileUpload(
                video_path,
                mimetype="video/mp4",
                chunksize=10 * 1024 * 1024,  # 10 MB chunks
                resumable=True,
            )
            logger.info(f"Uploading '{title}' to YouTube as {privacy} ...")

            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    pct = int(status.progress() * 100)
                    logger.info(f"YouTube upload {pct}%")

            video_id = response.get("id", "")
            if not video_id:
                return f"ERROR: Upload succeeded but no video ID returned: {response}"

            url = f"https://youtu.be/{video_id}"
            logger.info(f"Upload complete: {url}")
            return url

        except Exception as e:
            logger.exception(f"YouTube upload failed: {e}")
            return f"ERROR: YouTube upload failed — {e}"

    # ── Credential resolution ──────────────────────────────────────────────────

    def _get_credentials(self):
        """
        Return valid Google OAuth credentials.
        Priority:
          1. Per-user refresh token from config/env (multi-tenant SaaS mode)
          2. token.pickle (legacy CLI single-user mode)
          3. InstalledAppFlow browser flow (first-time CLI setup)
        """
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        # ── Mode 1: Per-user refresh token ─────────────────────────────────────
        refresh_token = self._get_per_user_refresh_token()
        if refresh_token:
            return self._creds_from_refresh_token(refresh_token)

        # ── Mode 2: Legacy token.pickle ────────────────────────────────────────
        token_path = os.path.join(BASE_DIR, "token.pickle")
        creds = None
        if os.path.exists(token_path):
            try:
                with open(token_path, "rb") as f:
                    creds = pickle.load(f)
                logger.info("Loaded credentials from token.pickle")
            except Exception as e:
                logger.warning(f"Could not load token.pickle: {e}")

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, "wb") as f:
                    pickle.dump(creds, f)
                logger.info("Refreshed token.pickle credentials")
                return creds
            except Exception as e:
                logger.warning(f"Token refresh failed: {e}")

        # ── Mode 3: Browser consent flow (CLI first-run only) ──────────────────
        secrets_candidates = [
            os.path.join(BASE_DIR, "client_secrets.json"),
            os.path.join(BASE_DIR, "client_secret.json"),
        ]
        secrets_path = next((p for p in secrets_candidates if os.path.exists(p)), None)

        if not secrets_path:
            logger.error(
                "No YouTube credentials found. Either:\n"
                "  • Set YOUTUBE_REFRESH_TOKEN env var (SaaS mode), or\n"
                "  • Place client_secrets.json in the project root (CLI mode)"
            )
            return None

        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(secrets_path, SCOPES)
            creds = flow.run_local_server(port=0)
            with open(token_path, "wb") as f:
                pickle.dump(creds, f)
            logger.info("New credentials obtained via browser, saved to token.pickle")
            return creds
        except Exception as e:
            logger.error(f"OAuth flow failed: {e}")
            return None

    def _get_per_user_refresh_token(self) -> Optional[str]:
        """Get the per-user refresh token from config or environment."""
        # Try config singleton (patched by crew_compat for SaaS mode)
        try:
            from config import get_config
            token = get_config().youtube_refresh_token
            if token:
                return token
        except Exception:
            pass

        # Try environment variable (set explicitly for testing)
        return os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

    def _creds_from_refresh_token(self, refresh_token: str):
        """Build a Credentials object from a stored refresh token."""
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        # Read client ID/secret from env or client_secrets.json
        client_id = os.environ.get("YOUTUBE_CLIENT_ID", "")
        client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "")

        if not client_id or not client_secret:
            # Try loading from client_secrets.json
            secrets_candidates = [
                os.path.join(BASE_DIR, "client_secrets.json"),
                os.path.join(BASE_DIR, "client_secret.json"),
            ]
            for p in secrets_candidates:
                if os.path.exists(p):
                    try:
                        import json
                        with open(p) as f:
                            data = json.load(f)
                        info = data.get("web", data.get("installed", {}))
                        client_id = info.get("client_id", "")
                        client_secret = info.get("client_secret", "")
                        break
                    except Exception:
                        pass

        if not client_id or not client_secret:
            raise RuntimeError(
                "YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set for per-user OAuth."
            )

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=None,   # Don't constrain — scope is whatever was originally granted
        )

        # Force immediate refresh to get a valid access token
        creds.refresh(Request())
        logger.info("Per-user YouTube credentials obtained from refresh token")
        return creds
