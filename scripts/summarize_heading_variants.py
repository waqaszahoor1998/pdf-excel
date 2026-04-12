#!/usr/bin/env python3
"""
Summarize heading/section-title wording differences across a local PDF corpus.

Privacy:
- This script intentionally avoids printing table cell values.
- It redacts likely account identifiers and long numbers from headings.

Usage:
  python scripts/summarize_heading_variants.py "/path/to/pdf/folder" --max-pages 25 --out docs/HEADING_VARIANTS_REPORT.md
"""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

import sys

# Ensure project root is importable when running as a script
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tables_to_excel import extract_sections_from_pdf  # noqa: E402


_MONEY_RE = re.compile(r"\$\s*[0-9][0-9,]*?(?:\.[0-9]{2})?")
_LONG_NUM_RE = re.compile(r"\b\d[\d\-_/.]{5,}\b")
# Alnum IDs like E79271004, G41269004, etc.
# Match embedded IDs even when followed by "_" or other non-alnum.
_ALNUM_ID_RE = re.compile(r"(?i)(?<![a-z0-9])[a-z]{1,5}\d{5,}(?![a-z0-9])")


def _redact(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    s = _MONEY_RE.sub("[AMT]", s)
    s = _LONG_NUM_RE.sub("[ID]", s)
    s = _ALNUM_ID_RE.sub("[ID]", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\bpage\s*\d+\s*(of\s*\d+)?\b", "", s, flags=re.I).strip()
    return s


def _keyish(s: str) -> str:
    s = _redact(s).lower()
    s = re.sub(r"[^a-z0-9%()&/\- ]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _doc_type_from_filename(name: str) -> str:
    n = name.lower()
    if "1099" in n:
        return "tax_1099"
    if "combined statement" in n:
        return "combined_statement"
    if "gsgov" in n or "gov fi" in n:
        return "gs_statement_gov_fi"
    if "gsmuni" in n or "muni fi" in n:
        return "gs_statement_muni_fi"
    if "prefd" in n or "hybrid" in n:
        return "gs_statement_pref_hybrid"
    if "cashmgmt" in n or "cash mgmt" in n:
        return "admin_trust_cash_mgmt"
    if "selfdirected" in n or "self-directed" in n:
        return "admin_trust_self_directed"
    return "other_statement"


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize section/heading wording variants across PDFs.")
    ap.add_argument("pdf_dir", type=Path, help="Directory containing PDFs")
    ap.add_argument("--max-pages", type=int, default=25, help="Max pages per PDF to scan (faster)")
    ap.add_argument("--out", type=Path, default=None, help="Write markdown report to this path")
    args = ap.parse_args()

    pdf_dir = args.pdf_dir.expanduser().resolve()
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in {pdf_dir}")

    by_type: dict[str, list[Path]] = defaultdict(list)
    for p in pdfs:
        by_type[_doc_type_from_filename(p.name)].append(p)

    heading_groups: dict[str, Counter[str]] = defaultdict(Counter)
    secname_groups: dict[str, Counter[str]] = defaultdict(Counter)
    per_doc: dict[str, dict] = {}

    for pdf in pdfs:
        secs = extract_sections_from_pdf(str(pdf), max_pages=args.max_pages)
        sec_names: list[str] = []
        heading_lines: list[str] = []
        for s in secs:
            sec_name = _redact(str(s[0] or ""))
            if sec_name:
                sec_names.append(sec_name)
                secname_groups[_keyish(sec_name)][sec_name] += 1
            for h in (s[1] or []):
                hh = _redact(str(h or ""))
                if hh:
                    heading_lines.append(hh)
                    heading_groups[_keyish(hh)][hh] += 1
        per_doc[pdf.name] = {
            "type": _doc_type_from_filename(pdf.name),
            "top_section_names": [x for x, _ in Counter(sec_names).most_common(20)],
            "top_heading_lines": [x for x, _ in Counter(heading_lines).most_common(20)],
        }

    def md() -> str:
        lines: list[str] = []
        lines.append("# Heading and section wording variants (corpus report)")
        lines.append("")
        lines.append("This report summarizes **section titles / heading lines** detected by the library extractor.")
        lines.append("It is intended to help with **template mapping** and **document-type routing**.")
        lines.append("")
        lines.append("## Corpus overview")
        lines.append("")
        lines.append(f"- **PDF directory**: `{pdf_dir}`")
        lines.append(f"- **PDFs scanned**: {len(pdfs)} (first {args.max_pages} pages each)")
        lines.append(f"- **Doc-type buckets (by filename heuristic)**: { {k: len(v) for k, v in sorted(by_type.items())} }")
        lines.append("")
        lines.append("## Common heading-line groups (with wording variants)")
        lines.append("")
        lines.append("Each group is a normalized key → the most common observed phrasings.")
        lines.append("")
        common = sorted(heading_groups.items(), key=lambda kv: sum(kv[1].values()), reverse=True)[:40]
        for k, ctr in common:
            examples = ", ".join([f"{v} (×{n})" for v, n in ctr.most_common(5)])
            if not k:
                continue
            lines.append(f"- **{k}**: {examples}")
        lines.append("")
        lines.append("## Common section-name groups (with wording variants)")
        lines.append("")
        common_s = sorted(secname_groups.items(), key=lambda kv: sum(kv[1].values()), reverse=True)[:40]
        for k, ctr in common_s:
            examples = ", ".join([f"{v} (×{n})" for v, n in ctr.most_common(5)])
            if not k:
                continue
            lines.append(f"- **{k}**: {examples}")
        lines.append("")
        lines.append("## Per-document quick view (top titles only)")
        lines.append("")
        for name in sorted(per_doc.keys()):
            d = per_doc[name]
            lines.append(f"### {name}")
            lines.append(f"- **bucket**: `{d['type']}`")
            lines.append(f"- **top section names**: {', '.join(d['top_section_names'][:10])}")
            lines.append(f"- **top heading lines**: {', '.join(d['top_heading_lines'][:10])}")
            lines.append("")
        return "\n".join(lines) + "\n"

    out = md()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(out, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

