#!/usr/bin/env bash
# Local preview server for the AcademindTube bilingual subtitle player.
#
#   ./serve.sh              rebuild the page from the SRT files, then serve it
#   ./serve.sh --no-build   skip the rebuild, just serve what's on disk
#
# Override defaults with env vars:  PORT=9000 WINDOW=3m ./serve.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8777}"
WINDOW="${WINDOW:-1m}"
HOST="${HOST:-127.0.0.1}"

# Prefer the managed venv (project convention), fall back to any python3.
PY="${PY:-/Users/feng33/.workbuddy-ai/binaries/python/envs/default/bin/python}"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3 || true)"
fi
if [ -z "$PY" ]; then
  echo "error: no python3 found; set PY=/path/to/python3" >&2
  exit 1
fi

SKIP_BUILD=0
for arg in "$@"; do
  case "$arg" in
    --no-build) SKIP_BUILD=1 ;;
    -h|--help) sed -n '2,8p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [ "$SKIP_BUILD" -eq 0 ]; then
  echo "==> rebuilding preview (window: $WINDOW)"
  (cd "$ROOT/scripts" && "$PY" build_preview.py --window "$WINDOW")
else
  echo "==> skipping rebuild (--no-build)"
fi

if [ ! -f "$ROOT/preview/index.html" ]; then
  echo "error: preview/index.html missing; run without --no-build" >&2
  exit 1
fi

URL="http://$HOST:$PORT/"
echo "==> serving $ROOT/preview  ->  $URL"
echo "    Ctrl-C to stop"

# Open the default browser (macOS). Harmless if it fails.
command -v open >/dev/null 2>&1 && open "$URL" || true

exec "$PY" -m http.server "$PORT" --bind "$HOST" --directory "$ROOT/preview"
