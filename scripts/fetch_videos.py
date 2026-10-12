"""Enumerate the @academind channel and filter videos by time window.

Uses yt-dlp to read the channel's video tab. `youtubetab:approximate_date`
yields upload dates in the flat listing, which is fast and good enough for
window filtering. Exact dates can be resolved per-video with --verify.
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys

from config import CHANNEL_URL, DATA, WINDOWS, load_json, save_json

RAW_PATH = DATA / "channel_videos.json"


def fetch_channel() -> list[dict]:
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--extractor-args", "youtubetab:approximate_date",
        "--print", "%(upload_date)s|%(id)s|%(title)s",
        CHANNEL_URL,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    videos = []
    for line in out.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        date, vid, title = parts
        videos.append({"id": vid, "title": title, "date": date})
    return videos


def verify_dates(videos: list[dict]) -> list[dict]:
    """Resolve exact upload dates for a small set of videos."""
    ids = [v["id"] for v in videos]
    cmd = ["yt-dlp", "--skip-download", "--print", "%(id)s|%(upload_date)s"]
    cmd += [f"https://www.youtube.com/watch?v={i}" for i in ids]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    exact = {}
    for line in out.splitlines():
        if "|" in line:
            i, d = line.split("|", 1)
            if d and d != "NA":
                exact[i] = d
    for v in videos:
        if v["id"] in exact:
            v["date_exact"] = exact[v["id"]]
    return videos


def in_window(video: dict, days: int, ref: dt.date) -> bool:
    raw = video.get("date_exact") or video.get("date")
    if not raw or raw == "NA" or len(raw) != 8:
        return False
    d = dt.date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    return (ref - d).days <= days


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", choices=list(WINDOWS), help="emit data/window_<label>.json")
    ap.add_argument("--ref", help="reference date YYYY-MM-DD (default: today)")
    ap.add_argument("--verify", action="store_true", help="resolve exact dates for the window")
    args = ap.parse_args()

    ref = dt.date.fromisoformat(args.ref) if args.ref else dt.date.today()

    videos = fetch_channel()
    save_json(RAW_PATH, {"fetched": ref.isoformat(), "count": len(videos), "videos": videos})
    print(f"channel: {len(videos)} videos -> {RAW_PATH}")

    if not args.window:
        return 0

    days = WINDOWS[args.window]
    selected = [v for v in videos if in_window(v, days, ref)]
    if args.verify:
        selected = verify_dates(selected)
        selected = [v for v in selected if in_window(v, days, ref)]
    selected.sort(key=lambda v: v.get("date_exact") or v["date"], reverse=True)

    out_path = DATA / f"window_{args.window}.json"
    save_json(out_path, {"window": args.window, "days": days, "ref": ref.isoformat(),
                         "count": len(selected), "videos": selected})
    print(f"window {args.window} (<= {days}d from {ref}): {len(selected)} videos -> {out_path}")
    for v in selected:
        print(f"  {v.get('date_exact') or v['date']}  {v['id']}  {v['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
