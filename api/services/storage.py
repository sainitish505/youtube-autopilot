"""
api/services/storage.py — Cloudflare R2 (S3-compatible) file storage.

Uploads generated videos/audio/images to R2 and returns public CDN URLs.
Falls back to local file serving if R2 is not configured.
"""
import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "youtube-autopilot")
R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL", "")


def _get_client():
    try:
        import boto3
        return boto3.client(
            "s3",
            endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        )
    except Exception as e:
        logger.warning(f"R2 client init failed: {e}. Using local storage fallback.")
        return None


def upload_file(local_path: str, object_key: str) -> str:
    """
    Upload a local file to R2. Returns public CDN URL, or local path if R2 unavailable.

    Args:
        local_path: Absolute path to local file
        object_key: R2 object key (e.g. "{user_id}/{job_id}/scene_001.mp4")
    Returns:
        Public URL string
    """
    if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
        logger.warning("R2 not configured — returning local path")
        return f"file://{local_path}"

    client = _get_client()
    if client is None:
        return f"file://{local_path}"

    try:
        client.upload_file(
            local_path,
            R2_BUCKET_NAME,
            object_key,
            ExtraArgs={"ContentType": _content_type(local_path)},
        )
        if R2_PUBLIC_URL:
            return f"{R2_PUBLIC_URL.rstrip('/')}/{object_key}"
        return f"https://{R2_BUCKET_NAME}.{R2_ACCOUNT_ID}.r2.cloudflarestorage.com/{object_key}"
    except Exception as e:
        logger.error(f"R2 upload failed for {local_path}: {e}")
        return f"file://{local_path}"


def upload_job_outputs(user_id: str, job_id: str, output_dir: str) -> dict:
    """
    Upload all generated files from output_dir to R2.
    Returns dict of {filename: public_url}.
    """
    urls = {}
    for ext in ["*.mp4", "*.mp3", "*.png", "*.jpg"]:
        for f in Path(output_dir).rglob(ext):
            rel = f.relative_to(output_dir)
            key = f"{user_id}/{job_id}/{rel}"
            url = upload_file(str(f), key)
            urls[str(rel)] = url
            logger.info(f"Uploaded {rel} → {url}")
    return urls


def _content_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".mp4": "video/mp4",
        ".mp3": "audio/mpeg",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(ext, "application/octet-stream")
