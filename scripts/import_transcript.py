"""Save an already-completed AssemblyAI transcript into the local cache.

Usage: python import_transcript.py <video_id> <transcript_id>
"""
from __future__ import annotations

import sys

import requests

from config import ASSEMBLYAI_BASE, DATA, load_assemblyai_key, save_json

TRANSCRIPTS = DATA / "transcripts"


def main() -> int:
    video_id, tid = sys.argv[1], sys.argv[2]
    resp = requests.get(
        f"{ASSEMBLYAI_BASE}/transcript/{tid}",
        headers={"authorization": load_assemblyai_key()},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    result = {
        "id": video_id,
        "title": "",
        "text": data.get("text", ""),
        "language_code": data.get("language_code"),
        "audio_duration_s": data.get("audio_duration"),
        "utterances": [
            {"start": u["start"], "end": u["end"], "text": u["text"]}
            for u in (data.get("utterances") or [])
        ],
        "words": [
            {"start": w["start"], "end": w["end"],
             "text": w.get("punctuated_word") or w.get("text", "")}
            for w in (data.get("words") or [])
        ],
    }
    out = TRANSCRIPTS / f"{video_id}.json"
    save_json(out, result)
    print(f"saved {out}  ({len(result['words'])} words)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
