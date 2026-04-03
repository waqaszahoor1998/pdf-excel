#!/usr/bin/env python3
"""
Run library-path extraction + validation + PDF audit on PDFs under evaluation/public_pdfs/.

Reads evaluation/corpus.json to label each file by **category** (government form, academic, etc.)
so results are interpreted in context — the pipeline is optimized for broker-style statements, not every PDF shape.

Usage:
  python scripts/download_eval_pdfs.py    # fetch corpus (best effort)
  python scripts/evaluate_public_pdfs.py
  python scripts/evaluate_public_pdfs.py path/to/a.pdf path/to/b.pdf

Writes evaluation/results/last_eval.json and last_eval.md (gitignored dir).
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pdfplumber

from tables_to_excel import validate_extraction_json, evaluate_extraction_json_correctness
from pdf_to_qb import pdf_to_qb_excel
from pdf_json_audit import apply_audit_to_extraction_file


def _corpus_by_filename() -> dict[str, dict]:
    p = ROOT / "evaluation" / "corpus.json"
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for item in data.get("items", []):
        fn = item.get("file")
        if fn:
            out[fn] = item
    return out


def _page_count(pdf_path: Path) -> int | None:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return len(pdf.pages)
    except Exception:
        return None


def _total_rows(sections: list) -> int:
    n = 0
    for s in sections:
        rows = s.get("rows") if isinstance(s, dict) else None
        if isinstance(rows, list):
            n += len(rows)
    return n


def _eval_one(pdf_path: Path, corpus_meta: dict | None) -> dict:
    tmp = Path(tempfile.mkdtemp())
    json_path = tmp / "out.json"
    xlsx_path = tmp / "out.xlsx"
    audit_path = tmp / "audit.json"
    try:
        pdf_to_qb_excel(
            str(pdf_path),
            str(xlsx_path),
            overwrite=True,
            json_path_out=str(json_path),
            write_excel=False,
        )
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        sections = payload.get("sections") or []
        qc = evaluate_extraction_json_correctness(payload)
        val_errs: list[str] = []
        try:
            validate_extraction_json(payload)
        except Exception as e:
            val_errs.append(str(e))
        apply_audit_to_extraction_file(
            pdf_path,
            json_path,
            audit_pages=min(20, 9999),
            report_path=audit_path,
            silent=True,
        )
        aud_payload = json.loads(json_path.read_text(encoding="utf-8"))
        meta = aud_payload.get("meta") or {}
        aud_sum = meta.get("audit_summary") or {}
        report_txt = audit_path.read_text(encoding="utf-8") if audit_path.exists() else "{}"
        report_obj = json.loads(report_txt) if report_txt.strip() else {}
        summary = report_obj.get("summary") or {}

        row: dict = {
            "pdf": str(pdf_path.name),
            "category": (corpus_meta or {}).get("category", "unknown"),
            "corpus_id": (corpus_meta or {}).get("id"),
            "bytes": pdf_path.stat().st_size,
            "pages": _page_count(pdf_path),
            "sections": len(sections),
            "total_rows": _total_rows(sections),
            "qc_status": qc.get("status"),
            "qc_score": qc.get("quality_score"),
            "qc_errors_n": len(qc.get("errors") or []),
            "qc_warnings_n": len(qc.get("warnings") or []),
            "validation_failed": bool(val_errs),
            "audit_pages": aud_sum.get("pages_audited") or summary.get("pages_audited"),
            "audit_confidence_pct": aud_sum.get("confidence_pct"),
            "audit_passed": aud_sum.get("passed_automation"),
            "meta_generator": meta.get("generator"),
        }
        if corpus_meta and corpus_meta.get("note"):
            row["corpus_note"] = corpus_meta["note"]
        return row
    finally:
        for f in tmp.iterdir():
            f.unlink(missing_ok=True)
        tmp.rmdir()


def _write_markdown(path: Path, report: dict, rows: list[dict]) -> None:
    lines = [
        "# Extraction evaluation run",
        "",
        f"Generated (UTC): `{report.get('generated_at_utc')}`",
        "",
        "Interpretation: **high QC scores** on `synthetic_broker_like` and many broker PDFs; **lower scores** on academic or government forms are often expected — different layout assumptions. Use this matrix to prioritize **universal** improvements (shared heuristics) vs. **document-type** profiles (broker vs. form vs. paper).",
        "",
        "| PDF | Category | Pages | Sections | Rows | QC | Score | QC errs |",
        "|-----|----------|-------|----------|------|----|-------|---------|",
    ]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r.get('pdf', '?')} | — | — | — | — | ERROR | — | — |")
            continue
        lines.append(
            f"| {r['pdf']} | {r.get('category', '?')} | {r.get('pages') or '-'} | "
            f"{r.get('sections')} | {r.get('total_rows')} | {r.get('qc_status')} | "
            f"{r.get('qc_score') if r.get('qc_score') is not None else '-'} | {r.get('qc_errors_n')} |"
        )
    lines.extend(["", "## Corpus notes", ""])
    for r in rows:
        if r.get("corpus_note"):
            lines.append(f"- **{r['pdf']}** ({r.get('category')}): {r['corpus_note']}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    corpus = _corpus_by_filename()
    if len(sys.argv) > 1:
        pdfs = [Path(p).resolve() for p in sys.argv[1:] if Path(p).suffix.lower() == ".pdf"]
    else:
        d = ROOT / "evaluation" / "public_pdfs"
        pdfs = sorted(d.glob("*.pdf"))
    if not pdfs:
        print(
            "No PDFs found. Run: python scripts/download_eval_pdfs.py\n"
            "Then re-run, or add .pdf files under evaluation/public_pdfs/",
            file=sys.stderr,
        )
        return 1

    out_dir = ROOT / "evaluation" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for p in pdfs:
        if not p.exists():
            print(f"Skip missing: {p}", file=sys.stderr)
            continue
        meta = corpus.get(p.name)
        print(f"Evaluating {p.name} …", file=sys.stderr)
        try:
            rows.append(_eval_one(p, meta))
        except Exception as e:
            rows.append({"pdf": p.name, "category": (meta or {}).get("category"), "error": str(e)})

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "pdfs": rows,
    }
    out_json = out_dir / "last_eval.json"
    out_md = out_dir / "last_eval.md"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(out_md, report, rows)
    print(f"Wrote {out_json}\nWrote {out_md}\n", file=sys.stderr)

    print(f"{'PDF':<36} {'category':<22} {'pg':>8} {'sec':>6} {'QC':>10} {'score':>6} {'err':>4}")
    print("-" * 100)
    for r in rows:
        if "error" in r:
            print(f"{r.get('pdf','?'):<36} {str(r.get('category','')):<22} ERROR: {r['error'][:40]}")
            continue
        print(
            f"{r['pdf']:<36} {str(r.get('category','')):<22} {str(r.get('pages') or '-'):>8} "
            f"{r['sections']:>6} {str(r['qc_status']):>10} "
            f"{r.get('qc_score') if r.get('qc_score') is not None else -1:>6.3f} {r['qc_errors_n']:>4}"
        )
    print(
        "\nNext: read evaluation/results/last_eval.md. To broaden coverage, add more entries to "
        "evaluation/corpus.json (with URL) and run download_eval_pdfs.py.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
