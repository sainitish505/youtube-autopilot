"""
main.py — Entry point for YouTube Autopilot Agent v2.

Usage:
    python main.py
    python main.py --niche "AI breakthroughs"
    python main.py --dashboard
    python main.py --niche "space exploration" --dashboard
"""

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import datetime

# ── Bootstrap: make sure BASE_DIR is on the path ──────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import load_config

# ── Logging setup ──────────────────────────────────────────────────────────────
def setup_logging(logs_dir: str, log_level: str) -> logging.Logger:
    """Configure root logger to write to both console and a timestamped file."""
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(logs_dir, f"run_{timestamp}.log")

    level = getattr(logging, log_level.upper(), logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    return logging.getLogger("main")


BANNER = r"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          YouTube Autopilot Agent  v2.0  —  CEO-Driven Production            ║
║    Research • Script • Approve • Generate • Edit • Optimise • Upload        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="YouTube Autopilot Agent — autonomous AI video creator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --niche "quantum computing explained"
  python main.py --dashboard
  python main.py --niche "AI robotics 2025" --dashboard
        """,
    )
    parser.add_argument(
        "--niche",
        type=str,
        default=None,
        help="Override the default niche from config.yaml (e.g. 'AI breakthroughs').",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        default=False,
        help="Launch the Streamlit live dashboard alongside the agent.",
    )
    return parser.parse_args()


def launch_dashboard(base_dir: str) -> subprocess.Popen:
    """Start the Streamlit dashboard in a background subprocess."""
    dashboard_path = os.path.join(base_dir, "dashboard.py")
    cmd = [
        sys.executable, "-m", "streamlit", "run", dashboard_path,
        "--server.headless", "true",
        "--server.port", "8501",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=base_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Give Streamlit a moment to start
    time.sleep(3)
    print("  Dashboard running at: http://localhost:8501")
    return proc


def main() -> None:
    args = parse_args()

    # Load config (singleton)
    cfg = load_config(niche_override=args.niche)

    # Setup logging
    logger = setup_logging(cfg.logs_dir, cfg.log_level)

    print(BANNER)
    logger.info("YouTube Autopilot Agent v2 starting up.")
    logger.info(f"Niche   : {cfg.default_niche or '(auto-detect trending)'}")
    logger.info(f"Mode    : {'Autonomous' if cfg.autonomous_mode else 'Human-in-the-loop'}")
    logger.info(f"Max len : {cfg.max_video_minutes} minutes")
    logger.info(f"Privacy : {cfg.upload_privacy}")

    # Optionally start dashboard
    dashboard_proc = None
    if args.dashboard:
        logger.info("Launching Streamlit dashboard...")
        try:
            dashboard_proc = launch_dashboard(BASE_DIR)
            logger.info("Dashboard started at http://localhost:8501")
        except Exception as e:
            logger.warning(f"Could not start dashboard: {e}")

    # ── Run the CEO crew ───────────────────────────────────────────────────────
    youtube_url = None
    try:
        from crew import run_ceo_crew
        youtube_url = run_ceo_crew(cfg)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        print("\nInterrupted — exiting gracefully.")
    except Exception as e:
        logger.exception(f"Unhandled error in CEO crew: {e}")
        print(f"\nERROR: {e}")
        sys.exit(1)
    finally:
        if dashboard_proc is not None:
            logger.info("Shutting down dashboard process...")
            dashboard_proc.terminate()

    # ── Final output ──────────────────────────────────────────────────────────
    if youtube_url:
        print("\n" + "=" * 80)
        print(f"  VIDEO PUBLISHED SUCCESSFULLY")
        print(f"  YouTube URL: {youtube_url}")
        print("=" * 80 + "\n")
        logger.info(f"Pipeline complete. Published: {youtube_url}")
    else:
        print("\nPipeline finished without a YouTube URL (check logs).")
        logger.warning("Pipeline complete but no YouTube URL returned.")


if __name__ == "__main__":
    main()
