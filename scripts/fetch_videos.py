"""Enumerate the @academind channel and filter videos by time window.

Uses yt-dlp to read the channel's video tab. `youtubetab:approximate_date`
yields upload dates in the flat listing, which is fast and good enough for
window filtering. Exact dates can be resolved per-video with --verify.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys

from config import CHANNEL_URL, DATA, WINDOWS, load_json, save_json

RAW_PATH = DATA / "channel_videos.json"
META_PATH = DATA / "channel_meta.json"


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


def _resize(url: str | None, spec: str) -> str | None:
    """Swap the trailing size spec of a yt3/googleusercontent URL."""
    if not url or "=" not in url:
        return url
    return url.rsplit("=", 1)[0] + "=" + spec


def fetch_channel_meta() -> dict:
    """Resolve the real channel identity: name, handle, follower count, avatar, banner."""
    cmd = ["yt-dlp", "-J", "--flat-playlist", "--playlist-end", "1", CHANNEL_URL]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    thumbs = info.get("thumbnails") or []

    banner = avatar = None
    for t in thumbs:
        url, w, h = t.get("url", ""), t.get("width") or 0, t.get("height") or 0
        if t.get("id") == "banner_uncropped" or (w >= 1000 and 0 < h < 500 and w / max(h, 1) > 3):
            if w and w <= 2200 and (banner is None or w > banner[0]):
                banner = (w, url)
        if t.get("id") == "avatar_uncropped" or (w and w == h):
            if avatar is None or w > avatar[0]:
                avatar = (w, url)

    return {
        "name": info.get("channel") or info.get("uploader"),
        "handle": info.get("uploader_id"),
        "channel_id": info.get("channel_id"),
        "url": info.get("channel_url"),
        "follower_count": info.get("channel_follower_count"),
        "description": (info.get("description") or "").strip(),
        "avatar": _resize(avatar[1] if avatar else None, "s176"),
        "banner": banner[1] if banner else None,
    }


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

    try:
        meta = fetch_channel_meta()
        meta["indexed_count"] = len(videos)
        meta["fetched"] = ref.isoformat()
        save_json(META_PATH, meta)
        print(f"channel meta -> {META_PATH}  ({meta['name']}, "
              f"{meta['follower_count']} followers, {meta['indexed_count']} indexed)")
    except Exception as exc:  # never let identity lookup break the listing
        print(f"warning: could not fetch channel meta: {exc}", file=sys.stderr)

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
