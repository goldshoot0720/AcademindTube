"""Build bilingual (EN + zh-TW) SRT subtitle files from translated segments."""
from __future__ import annotations

import pathlib

from config import SUBS, slugify


_SENT_END = (".", "?", "!", "…")


def segments_from_words(words: list[dict], max_chars: int = 84,
                        max_dur_ms: int = 7000, max_gap_ms: int = 1200) -> list[dict]:
    """Group word-level timings into readable sentence segments."""
    segments: list[dict] = []
    cur: list[dict] = []

    def flush() -> None:
        if not cur:
            return
        segments.append({
            "start": cur[0]["start"],
            "end": cur[-1]["end"],
            "text": " ".join(w["text"] for w in cur).strip(),
        })
        cur.clear()

    for w in words:
        if cur:
            gap = w["start"] - cur[-1]["end"]
            dur = w["end"] - cur[0]["start"]
            chars = sum(len(x["text"]) + 1 for x in cur)
            if gap > max_gap_ms or dur > max_dur_ms or chars > max_chars:
                flush()
        cur.append(w)
        if w["text"].rstrip().endswith(_SENT_END):
            flush()
    flush()
    return segments


def _ts(ms: int) -> str:
    ms = max(0, int(ms))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_bilingual_srt(segments: list[dict]) -> str:
    blocks = []
    idx = 1
    for seg in segments:
        start = seg.get("start", 0)
        end = seg.get("end", start + 1000)
        if end <= start:
            end = start + 800
        en = (seg.get("text") or "").strip()
        zh = (seg.get("zh") or "").strip()
        if not en and not zh:
            continue
        body = "\n".join([t for t in (en, zh) if t])
        blocks.append(f"{idx}\n{_ts(start)} --> {_ts(end)}\n{body}\n")
        idx += 1
    return "\n".join(blocks)


def write_srt(video: dict, segments: list[dict], window: str) -> pathlib.Path:
    out_dir = SUBS / window
    out_dir.mkdir(parents=True, exist_ok=True)
    date = video.get("date_exact") or video.get("date") or ""
    slug = slugify(video["title"])
    name = f"{date}_{video['id']}_{slug}.srt" if date else f"{video['id']}_{slug}.srt"
    path = out_dir / name
    path.write_text(build_bilingual_srt(segments), encoding="utf-8")
    return path
