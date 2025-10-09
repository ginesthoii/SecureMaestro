import os
import tempfile
from pathlib import Path
from typing import Optional
from yt_dlp import YoutubeDL
from pydub import AudioSegment

from .security import validate_loop_request
from .utils_ffmpeg import run_ffmpeg, atempo_chain, ensure_ffmpeg

# Hard cap on final output seconds (defense-in-depth)
MAX_OUTPUT_SEC = 15 * 60  # 15 minutes


def _safe_temp_dir() -> tempfile.TemporaryDirectory:
    """Create an isolated temporary directory that auto-cleans on exit."""
    return tempfile.TemporaryDirectory(prefix="sm_", ignore_cleanup_errors=True)


def _download_youtube_audio(url: str, out_dir: Path, max_full_length_sec: int) -> Path:
    """Download best audio track from a YouTube URL into the given directory."""
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,

        # Chrome cookie access avoids bot-checks (replace with Safari if preferred)
        "cookiesfrombrowser": ("chrome",),
        "extractor_args": {"youtube": {"player_client": ["ios"]}},  # iOS client bypasses CAPTCHA checks
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        duration = info.get("duration") or 0
        if duration and duration > max_full_length_sec:
            raise ValueError(f"Video too long ({duration}s). Cap is {max_full_length_sec}s.")

        ydl.download([url])
        candidates = list(out_dir.glob("*"))
        if not candidates:
            raise RuntimeError("Download failed or produced no files.")
        return max(candidates, key=lambda p: p.stat().st_size)


def _ffmpeg_trim_speed(input_path: Path, start: float, end: float, speed: float, output_path: Path):
    """Trim and adjust playback speed using ffmpeg."""
    duration = end - start
    tempo_filter = atempo_chain(speed)
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-t", str(duration),
        "-i", str(input_path),
        "-filter:a", tempo_filter,
        str(output_path)
    ]
    run_ffmpeg(cmd)


def _repeat_segment(segment: AudioSegment, repeats: int, total_ms_cap: int) -> AudioSegment:
    """Repeat an AudioSegment in memory with a time safety cap."""
    output = AudioSegment.empty()
    for i in range(repeats):
        if len(output) + len(segment) > total_ms_cap:
            break
        output += segment
    return output


def youtube_practice_loop(
    url: str,
    start_sec: float,
    end_sec: float,
    speed: float,
    repeats: int,
    output_path: str,
    max_full_length_sec: int = 1200
) -> Path:
    """
    Main API for CLI. Downloads a YouTube clip, trims, adjusts speed, loops it, and exports to file.
    """
    req = validate_loop_request(
        url=url,
        start_sec=start_sec,
        end_sec=end_sec,
        speed=speed,
        repeats=repeats,
        max_full_length_sec=max_full_length_sec
    )

    if req.end_sec <= req.start_sec:
        raise ValueError("end_sec must be greater than start_sec.")

    ensure_ffmpeg()
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with _safe_temp_dir() as td:
        tdir = Path(td)

        # 1) Download
        audio_src = _download_youtube_audio(req.url, tdir, req.max_full_length_sec)

        # 2) Trim + speed → segment.wav
        seg_path = tdir / "segment.wav"
        _ffmpeg_trim_speed(audio_src, req.start_sec, req.end_sec, req.speed, seg_path)

        # 3) Repeat in-memory with pydub
        segment = AudioSegment.from_file(seg_path)
        total_ms_cap = MAX_OUTPUT_SEC * 1000
        looped = _repeat_segment(segment, req.repeats, total_ms_cap)

        # 4) Export (wav or mp3 depending on suffix)
        suffix = out_path.suffix.lower()
        if suffix == ".mp3":
            looped.export(out_path, format="mp3", bitrate="192k")
        else:
            looped.export(out_path, format="wav")

        return out_path