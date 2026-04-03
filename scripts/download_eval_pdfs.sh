#!/usr/bin/env bash
# Wrapper: fetch evaluation corpus via Python (see evaluation/corpus.json).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$ROOT/scripts/download_eval_pdfs.py" "$@"
