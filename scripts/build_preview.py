"""Build the local bilingual-subtitle preview.

Parses the SRT files under `subtitles/<window>/`, pairs them with the video
metadata in `data/window_<window>.json`, and emits:

  preview/subtitles.json   parsed cues (machine-readable, for other tooling)
  preview/index.html       self-contained player page (data inlined, so it
                           works from file:// as well as over HTTP)

Usage (from scripts/):  python build_preview.py [--window 1m]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys

from config import DATA, ROOT, SUBS, load_json

PREVIEW = ROOT / "preview"
TEMPLATE = PREVIEW / "app.template.html"
TRANSCRIPTS = DATA / "transcripts"
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef]")

# index / start --> end / body
_BLOCK = re.compile(
    r"(\d+)\s*\n"
    r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n"
    r"(.*?)(?=\n\s*\n|\Z)",
    re.S,
)


def _to_seconds(ts: str) -> float:
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_srt(text: str) -> list[dict]:
    """Return [{start, end, en, zh}] — lines with CJK go to zh, the rest to en."""
    cues: list[dict] = []
    for idx, start, end, body in _BLOCK.findall(text):
        en_lines, zh_lines = [], []
        for line in body.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            (zh_lines if CJK.search(line) else en_lines).append(line)
        cues.append({
            "i": int(idx),
            "start": round(_to_seconds(start), 3),
            "end": round(_to_seconds(end), 3),
            "en": " ".join(en_lines),
            "zh": " ".join(zh_lines),
        })
    return cues


def find_srt(window: str, video_id: str) -> pathlib.Path | None:
    matches = sorted((SUBS / window).glob(f"*_{video_id}_*.srt"))
    return matches[0] if matches else None


def build(window: str) -> dict:
    win_path = DATA / f"window_{window}.json"
    payload = json.loads(win_path.read_text())
    videos = []

    for video in payload["videos"]:
        srt = find_srt(window, video["id"])
        if not srt:
            print(f"  ! no SRT for {video['id']} — skipped", file=sys.stderr)
            continue
        cues = parse_srt(srt.read_text(encoding="utf-8"))
        issues = sum(1 for c in cues if not c["en"] or not c["zh"])
        # Prefer the real audio length (AssemblyAI's audio_duration_s) so the
        # displayed duration matches YouTube; the last cue's end runs 1-2s short.
        transcript = load_json(TRANSCRIPTS / f"{video['id']}.json", {}) or {}
        duration = transcript.get("audio_duration_s") or (cues[-1]["end"] if cues else 0)
        videos.append({
            "id": video["id"],
            "title": video["title"],
            "date": video.get("date_exact") or video.get("date") or "",
            "file": srt.name,
            "cueCount": len(cues),
            "issues": issues,
            "duration": duration,
            "cues": cues,
        })
        flag = f"  ({issues} 筆未翻譯)" if issues else ""
        print(f"  {video['id']}  {len(cues):>4} cues  {srt.name}{flag}")

    channel = load_json(DATA / "channel_meta.json", {}) or {}

    return {
        "window": window,
        "days": payload.get("days"),
        "ref": payload.get("ref"),
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "channel": channel,
        "videos": videos,
    }


def write_html(data: dict) -> pathlib.Path:
    html = TEMPLATE.read_text(encoding="utf-8")
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    out = PREVIEW / "index.html"
    out.write_text(html.replace("__SUBTITLES_DATA__", blob), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default="1m")
    args = ap.parse_args()

    print(f"building preview for window {args.window}")
    data = build(args.window)
    if not data["videos"]:
        raise SystemExit("no SRT files found; run pipeline.py first")

    (PREVIEW / "subtitles.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    html = write_html(data)

    total = sum(v["cueCount"] for v in data["videos"])
    print(f"\n{len(data['videos'])} video(s), {total} cues -> {html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
