"""Shared configuration and helpers for the AcademindTube subtitle pipeline."""
from __future__ import annotations

import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
AUDIO = ROOT / "audio"
SUBS = ROOT / "subtitles"
SECRETS = ROOT / ".secrets"

CHANNEL_URL = "https://www.youtube.com/@academind/videos"

# Window label -> number of days to look back (from "now").
WINDOWS = {
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
    "3y": 1095,
}

ASSEMBLYAI_BASE = "https://api.assemblyai.com/v2"
GOOGLE_TRANSLATE = "https://translate.googleapis.com/translate_a/single"


def load_assemblyai_key() -> str:
    """Prefer an env var, fall back to the local (gitignored) secret file."""
    env = os.environ.get("ASSEMBLYAI_API_KEY")
    if env and env.strip():
        return env.strip()
    path = SECRETS / "assemblyai.key"
    if path.exists():
        return path.read_text().strip()
    raise RuntimeError(
        "AssemblyAI API key not found. Set ASSEMBLYAI_API_KEY or create "
        f"{path}."
    )


def slugify(title: str, max_len: int = 60) -> str:
    keep = []
    for ch in title.lower():
        if ch.isalnum():
            keep.append(ch)
        elif ch in " -_":
            keep.append("-")
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:max_len].strip("-")


def load_json(path: pathlib.Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def save_json(path: pathlib.Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
