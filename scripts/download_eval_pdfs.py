#!/usr/bin/env python3
"""
Download the evaluation corpus listed in evaluation/corpus.json into evaluation/public_pdfs/.

Uses a browser-like User-Agent where needed. Some hosts (SEC, CDNs) may still return 403 — download those manually.

Usage:
  python scripts/download_eval_pdfs.py
  python scripts/download_eval_pdfs.py --force   # re-download even if file exists
"""

from __future__ import annotations

import argparse
import json
import shutil
import ssl
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evaluation" / "corpus.json"
OUT_DIR = ROOT / "evaluation" / "public_pdfs"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _fetch(url: str, dest: Path) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            data = resp.read()
        if len(data) < 500 or not data.startswith(b"%PDF"):
            print(f"  SKIP {dest.name}: not a PDF ({len(data)} bytes)", file=sys.stderr)
            return False
        dest.write_bytes(data)
        return True
    except Exception as e:
        print(f"  FAIL {dest.name}: {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Download evaluation PDF corpus.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Tiny synthetic sample
    sample_script = ROOT / "scripts" / "make_sample_pdf.py"
    sample_out = ROOT / "sample_report.pdf"
    generated = OUT_DIR / "generated_sample_report.pdf"
    if sample_script.exists():
        import subprocess

        subprocess.run([sys.executable, str(sample_script)], cwd=str(ROOT), check=False)
        if sample_out.exists():
            shutil.copyfile(sample_out, generated)
            print(f"OK {generated.name} (from make_sample_pdf)")

    ok = 0
    fail = 0
    for item in corpus.get("items", []):
        fname = item.get("file")
        if not fname:
            continue
        dest = OUT_DIR / fname
        if item.get("source") == "local":
            continue
        url = item.get("url")
        if not url:
            continue
        if dest.exists() and not args.force:
            print(f"SKIP {fname} (exists, use --force)")
            continue
        print(f"GET {fname} …")
        if _fetch(url, dest):
            print(f"  OK {dest.stat().st_size} bytes")
            ok += 1
        else:
            fail += 1

    print(f"\nDownloaded: {ok}, failed: {fail}. See evaluation/README.md for manual fallback.")
    return 0 if ok > 0 or fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
