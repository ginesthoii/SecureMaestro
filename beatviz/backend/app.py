import os, re, json, tempfile, shutil, uuid, subprocess, math
from typing import List
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import librosa
import soundfile as sf

YTDLP_MAX_FILESIZE = "50M"     # skip massive videos
MAX_DURATION_SEC = 15 * 60     # 15 min cap

app = FastAPI(title="SecureMaestro Beat API", version="0.1")

# CORS for local demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

YOUTUBE_RE = re.compile(r"^https?://(www\.)?(youtube\.com|youtu\.be)/")

class BeatResponse(BaseModel):
    video_id: str
    sr: int
    bpm_estimate: float
    beats: List[float]     # seconds
    onsets: List[float]    # seconds (optional extra for visual feel)

def _run(cmd: list):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip())
    return p.stdout

def _extract_video_id(url: str) -> str:
    # simple extraction (not perfect, but fine for demo)
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    return str(uuid.uuid4())[:8]

@app.get("/api/analyze", response_model=BeatResponse)
def analyze(url: str = Query(..., description="YouTube URL")):
    # 1) Validate URL
    if not YOUTUBE_RE.match(url):
        raise HTTPException(400, "Provide a valid YouTube URL (http/https).")
    if any(x in url for x in ["&list=", "playlist?"]):
        raise HTTPException(400, "Playlists not supported; submit a single video URL.")

    workdir = tempfile.mkdtemp(prefix="sm-")
    try:
        vid = _extract_video_id(url)
        out_audio = os.path.join(workdir, f"{vid}.wav")

        # 2) yt-dlp: fetch bestaudio, cap filesize, postprocess to wav mono 22050
        ytdlp_cmd = [
            "yt-dlp",
            "--no-playlist",
            "--max-filesize", YTDLP_MAX_FILESIZE,
            "-x", "--audio-format", "wav",
            "--audio-quality", "0",
            "-o", os.path.join(workdir, "%(id)s.%(ext)s"),
            url
        ]
        _run(ytdlp_cmd)

        # find the produced wav (yt-dlp names by ID)
        wavs = [f for f in os.listdir(workdir) if f.endswith(".wav")]
        if not wavs:
            raise HTTPException(415, "Could not retrieve audio stream.")
        raw_wav = os.path.join(workdir, wavs[0])

        # 3) Normalize to mono 22050Hz with ffmpeg (defensive)
        _run(["ffmpeg", "-y", "-i", raw_wav, "-ac", "1", "-ar", "22050", out_audio])

        # 4) Duration cap check
        with sf.SoundFile(out_audio) as f:
            duration = len(f) / f.samplerate
            if duration > MAX_DURATION_SEC:
                raise HTTPException(413, f"Video too long (> {MAX_DURATION_SEC//60} min).")

        # 5) Librosa beat + onset analysis
        y, sr = librosa.load(out_audio, sr=None, mono=True)
        # onset strength for "bounce energy"
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units='time')

        # tempo + beats with dynamic programming
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units='frames')
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)

        # Optional: prune overly-dense beats (very noisy tracks)
        pruned = []
        last = -10
        for t in beat_times:
            if t - last >= 0.15:  # >= 150ms apart
                pruned.append(float(t))
                last = t

        return BeatResponse(
            video_id=vid,
            sr=sr,
            bpm_estimate=float(tempo) if isinstance(tempo, (int, float, np.floating)) else float(tempo[0]),
            beats=[float(t) for t in pruned],
            onsets=[float(t) for t in onsets]
        )
    except RuntimeError as e:
        msg = str(e)
        if "File is larger than max-filesize" in msg:
            raise HTTPException(413, "Audio too large for demo limits.")
        raise HTTPException(500, f"Processing error: {msg}")
    finally:
        # 6) Clean temp dir (no lingering user data)
        shutil.rmtree(workdir, ignore_errors=True)