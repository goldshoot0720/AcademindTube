"""Download audio and transcribe it with AssemblyAI.

Produces, per video, data/transcripts/<video_id>.json containing the full text
plus sentence-level `utterances` (start/end ms + text) used for subtitles.
"""
from __future__ import annotations

import pathlib
import subprocess
import time

import requests

from config import AUDIO, ASSEMBLYAI_BASE, DATA, load_assemblyai_key

TRANSCRIPTS = DATA / "transcripts"


def download_audio(video_id: str, force: bool = False) -> pathlib.Path:
    AUDIO.mkdir(parents=True, exist_ok=True)
    existing = list(AUDIO.glob(f"{video_id}.*"))
    if existing and not force:
        return existing[0]
    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = [
        "yt-dlp",
        "-f", "bestaudio/best",
        "--no-playlist",
        "-o", str(AUDIO / "%(id)s.%(ext)s"),
        url,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    files = list(AUDIO.glob(f"{video_id}.*"))
    if not files:
        raise RuntimeError(f"audio download failed for {video_id}")
    return files[0]


def _headers() -> dict:
    return {"authorization": load_assemblyai_key()}


def upload_audio(path: pathlib.Path) -> str:
    with open(path, "rb") as fh:
        resp = requests.post(
            f"{ASSEMBLYAI_BASE}/upload",
            headers=_headers(),
            data=fh,
            timeout=600,
        )
    resp.raise_for_status()
    return resp.json()["upload_url"]


def create_transcript(audio_url: str, language_code: str = "en") -> str:
    resp = requests.post(
        f"{ASSEMBLYAI_BASE}/transcript",
        headers=_headers(),
        json={"audio_url": audio_url, "language_code": language_code},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def poll_transcript(transcript_id: str, timeout_s: int = 3600) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = requests.get(
            f"{ASSEMBLYAI_BASE}/transcript/{transcript_id}",
            headers=_headers(),
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status == "completed":
            return data
        if status == "error":
            raise RuntimeError(f"AssemblyAI error: {data.get('error')}")
        time.sleep(10)
    raise TimeoutError(f"transcript {transcript_id} timed out")


def transcribe_video(video: dict, force: bool = False) -> dict:
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    out_path = TRANSCRIPTS / f"{video['id']}.json"
    if out_path.exists() and not force:
        return __import__("json").loads(out_path.read_text())

    audio = download_audio(video["id"], force=force)
    upload_url = upload_audio(audio)
    tid = create_transcript(upload_url)
    data = poll_transcript(tid)
    utterances = [
        {"start": u["start"], "end": u["end"], "text": u["text"]}
        for u in (data.get("utterances") or [])
    ]
    words = [
        {"start": w["start"], "end": w["end"],
         "text": w.get("punctuated_word") or w.get("text", "")}
        for w in (data.get("words") or [])
    ]
    result = {
        "id": video["id"],
        "title": video["title"],
        "text": data.get("text", ""),
        "language_code": data.get("language_code"),
        "audio_duration_s": data.get("audio_duration"),
        "utterances": utterances,
        "words": words,
    }
    out_path.write_text(__import__("json").dumps(result, ensure_ascii=False, indent=2))
    return result
