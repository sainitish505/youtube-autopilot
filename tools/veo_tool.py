import time
import os
import requests
from pathlib import Path
from crewai.tools import BaseTool
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class VeoVideoTool(BaseTool):
    name: str = "Veo 3.1 Video Generator"
    description: str = "Generates a high-quality vertical YouTube Short video using OpenAI Sora. Input: detailed prompt. Returns: path to saved MP4 file."

    def _run(self, prompt: str) -> str:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        print("🚀 Sending prompt to OpenAI Sora...")

        video = client.videos.create_and_poll(
            model="sora-2",
            prompt=prompt,
            size="720x1280",   # Vertical 9:16 for YouTube Shorts
            seconds="8",       # 8-second Short
        )

        if video.status == "completed":
            # Download the video content
            content = client.videos.download_content(video.id)

            output_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "output" / "videos"
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = int(time.time())
            output_path = output_dir / f"sora_short_{timestamp}.mp4"

            with open(output_path, "wb") as f:
                f.write(content.read())

            print(f"✅ Video saved: {output_path}")
            return str(output_path)
        else:
            return f"ERROR: Video generation failed with status: {video.status}. Error: {video.error}"
