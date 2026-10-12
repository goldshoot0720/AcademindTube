"""End-to-end orchestrator: window -> transcribe -> translate -> bilingual SRT."""
from __future__ import annotations

import argparse
import sys

from build_srt import segments_from_words, write_srt
from config import DATA, WINDOWS, load_json
from transcribe import transcribe_video
from translate import translate_segments


def run_window(window: str, limit: int | None = None, force: bool = False) -> list[str]:
    win_path = DATA / f"window_{window}.json"
    payload = load_json(win_path)
    if not payload:
        raise SystemExit(f"missing {win_path}; run fetch_videos.py --window {window} first")

    videos = payload["videos"]
    if limit:
        videos = videos[:limit]

    written = []
    for i, video in enumerate(videos, 1):
        print(f"[{i}/{len(videos)}] {video['id']}  {video['title']}", flush=True)
        transcript = transcribe_video(video, force=force)
        segments = transcript.get("utterances") or []
        if not segments:
            segments = segments_from_words(transcript.get("words") or [])
        if not segments and transcript.get("text"):
            segments = [{"start": 0, "end": 0, "text": transcript["text"]}]
        translated = translate_segments(video["id"], segments, force=force)
        path = write_srt(video, translated, window)
        written.append(str(path))
        print(f"    -> {path}  ({len(translated)} cues)", flush=True)
    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", required=True, choices=list(WINDOWS))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--force", action="store_true", help="ignore caches")
    args = ap.parse_args()
    written = run_window(args.window, limit=args.limit, force=args.force)
    print(f"\ndone: {len(written)} subtitle file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
