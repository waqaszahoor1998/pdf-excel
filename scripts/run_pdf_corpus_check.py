#!/usr/bin/env python3
"""
Regression helper: run library extraction + JSON validation on a folder of PDFs.

Usage:
  PDF_CORPUS_DIR=/path/to/pdfs python scripts/run_pdf_corpus_check.py
  python scripts/run_pdf_corpus_check.py /path/to/pdfs
  python scripts/run_pdf_corpus_check.py /path/to/pdfs --max-pages 12

Does not print cell values (privacy). Exits 1 if any file has validation status "failed".

Keep sensitive PDFs out of git; paths are local only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tables_to_excel import (  # noqa: E402
    evaluate_extraction_json_correctness,
    extract_sections_from_pdf,
    _sections_to_json_serializable,
    refine_json_sections,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Batch-check PDF corpus extraction quality.")
    ap.add_argument(
        "corpus_dir",
        nargs="?",
        default=os.environ.get("PDF_CORPUS_DIR", ""),
        help="Folder of PDFs (or set PDF_CORPUS_DIR)",
    )
    ap.add_argument("--max-pages", type=int, default=None, help="Limit pages per PDF (faster smoke).")
    ap.add_argument("--json-out", type=Path, default=None, help="Optional path to write summary JSON report.")
    args = ap.parse_args()
    corpus = (args.corpus_dir or "").strip()
    if not corpus:
        print("Set PDF_CORPUS_DIR or pass corpus directory.", file=sys.stderr)
        return 2
    d = Path(corpus).expanduser().resolve()
    if not d.is_dir():
        print(f"Not a directory: {d}", file=sys.stderr)
        return 2

    pdfs = sorted(d.glob("*.pdf"))
    if not pdfs:
        print(f"No PDF files in {d}", file=sys.stderr)
        return 2

    rows: list[dict] = []
    any_failed = False
    for pdf in pdfs:
        try:
            sections = extract_sections_from_pdf(str(pdf), max_pages=args.max_pages)
            payload = {"sections": refine_json_sections(_sections_to_json_serializable(sections))}
            ev = evaluate_extraction_json_correctness(payload)
            st = ev.get("status") or "unknown"
            if st == "failed":
                any_failed = True
            rows.append(
                {
                    "file": pdf.name,
                    "sections": len(sections),
                    "status": st,
                    "quality_score": ev.get("quality_score"),
                    "error_count": len(ev.get("errors") or []),
                    "warning_count": len(ev.get("warnings") or []),
                }
            )
        except Exception as e:
            any_failed = True
            rows.append({"file": pdf.name, "error": str(e)[:200]})

    # Console summary (no PII)
    w = max(len(r["file"]) for r in rows) + 2
    print(f"{'file':<{w}} status      score   sec")
    for r in rows:
        fn = r["file"]
        if "error" in r:
            print(f"{fn:<{w}} ERROR       —       —   ({r['error'][:60]})")
            continue
        print(
            f"{fn:<{w}} {r['status']:<11} {str(r.get('quality_score')):>5} {r['sections']:>5}"
        )

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps({"corpus_dir": str(d), "results": rows}, indent=2), encoding="utf-8")
        print(f"Wrote {args.json_out}")

    return 1 if any_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
