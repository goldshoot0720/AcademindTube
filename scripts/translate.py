"""English -> Traditional Chinese translation with on-disk caching.

Primary backend: Google's public `clients5` endpoint (fast, no key).
Fallback: the `translate_a/single` endpoint. Each segment is translated
independently and the cache is written incrementally, so runs are resumable.
"""
from __future__ import annotations

import json
import pathlib
import time

import requests

from config import DATA

CACHE_DIR = DATA / "translations"

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

_ENDPOINTS = [
    ("https://clients5.google.com/translate_a/t",
     lambda sl, tl, q: {"client": "dict-chrome-ex", "sl": sl, "tl": tl, "q": q}),
    ("https://translate.googleapis.com/translate_a/single",
     lambda sl, tl, q: {"client": "gtx", "sl": sl, "tl": tl, "dt": "t", "q": q}),
]


def _parse(payload) -> str:
    if isinstance(payload, list) and payload:
        if isinstance(payload[0], str):
            return "".join(payload)
        if isinstance(payload[0], list):
            return "".join(seg[0] for seg in payload[0] if seg and seg[0])
    return ""


def _translate_chunk(text: str, sl: str, tl: str, retries: int = 5) -> str:
    last_err = None
    for base, mk in _ENDPOINTS:
        for attempt in range(retries):
            try:
                resp = requests.get(
                    base, params=mk(sl, tl, text),
                    headers={"User-Agent": _UA}, timeout=30,
                )
                if resp.status_code == 429:
                    time.sleep(3.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                out = _parse(resp.json())
                if out:
                    return out
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"translation failed: {last_err}")


def translate_text(text: str, sl: str = "en", tl: str = "zh-TW") -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) <= 1800:
        return _translate_chunk(text, sl, tl)
    parts, buf = [], ""
    for sentence in text.replace("? ", "?\n").replace(". ", ".\n").split("\n"):
        if len(buf) + len(sentence) + 1 > 1800:
            parts.append(buf)
            buf = sentence
        else:
            buf = f"{buf} {sentence}".strip()
    if buf:
        parts.append(buf)
    return " ".join(_translate_chunk(p, sl, tl) for p in parts)


def translate_segments(video_id: str, segments: list[dict],
                       sl: str = "en", tl: str = "zh-TW",
                       force: bool = False) -> list[dict]:
    """Translate {start,end,text} segments, caching (and resuming) on disk."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{video_id}.{tl}.json"

    done: dict[tuple, str] = {}
    if cache_path.exists() and not force:
        for item in json.loads(cache_path.read_text()):
            done[(item["start"], item["end"])] = item.get("zh", "")

    out: list[dict] = []
    for seg in segments:
        key = (seg["start"], seg["end"])
        if done.get(key):
            out.append({**seg, "zh": done[key]})
            continue
        zh = translate_text(seg["text"], sl=sl, tl=tl)
        out.append({**seg, "zh": zh})
        cache_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
        time.sleep(0.25)  # be polite to the public endpoint
    return out
