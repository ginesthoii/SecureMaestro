import subprocess
import shutil
from pathlib import Path

def ensure_ffmpeg():
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH. Install ffmpeg first.")

def run_ffmpeg(args: list[str]) -> None:
    ensure_ffmpeg()
    completed = subprocess.run(["ffmpeg", "-y", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"ffmpeg error: {completed.stderr[:5000]}")

def atempo_chain(speed: float) -> list[str]:
    """
    FFmpeg atempo accepts 0.5..2.0 per filter; to achieve arbitrary speed, chain filters.
    For your MVP speeds (0.5, 0.7, 0.9) a single atempo is fine.
    """
    return [f"atempo={speed}"]