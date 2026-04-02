"""
PDF-vs-JSON audit (inspired by ~/Downloads/pdfxtract).

Goal: given a source PDF and our canonical extraction JSON (sections/headings/rows),
produce an evidence-based audit report:
  - numeric coverage gaps (numbers in PDF missing from JSON)
  - text coverage gaps (significant words in PDF missing from JSON)
  - structural issues (row width mismatch, empty sections, pages with content but no sections)
  - invented values (JSON cell values not present anywhere in PDF)

This complements internal JSON validation (row/column tallies) by comparing to the PDF.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF


# Financial-style number tokens: "27,947.11", "0.00", "-1,234", "12345"
_NUMBER_RE = re.compile(r"-?\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?")

# Only report missing numbers with >= this many digits (filters noise like "1", "2", page numbers).
_MIN_DIGITS_TO_REPORT = 3

# Minimum meaningful spans before a page with no sections is flagged.
_EMPTY_PAGE_SPAN_THRESHOLD = 10

# Common short words to skip in text coverage.
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "in",
        "on",
        "for",
        "to",
        "is",
        "be",
        "by",
        "at",
        "as",
        "with",
        "from",
        "that",
        "this",
        "was",
        "are",
        "it",
        "its",
        "not",
        "has",
        "no",
        "if",
        "all",
        "any",
        "per",
    }
)

# Values that may be synthesized; don't flag as invented.
_SYNTHETIC_VALUES = frozenset(
    {
        "Various",
        "See details",
        "Yes",
        "No",
        "A",
        "B",
        "C",
        "D",
        "E",
        "X",
    }
)


@dataclass(frozen=True)
class PdfSpan:
    text: str
    size: float


def _page_spans(page: fitz.Page) -> list[PdfSpan]:
    """
    Extract approximate spans (text fragments + font size) from a PDF page.
    We only need text and size to filter obvious noise.
    """
    out: list[PdfSpan] = []
    try:
        d = page.get_text("dict")
    except Exception:
        d = None
    if not d:
        return out
    for block in d.get("blocks", []) or []:
        for line in block.get("lines", []) or []:
            for span in line.get("spans", []) or []:
                t = span.get("text")
                if not isinstance(t, str) or not t.strip():
                    continue
                size = span.get("size")
                try:
                    sz = float(size) if size is not None else 7.0
                except Exception:
                    sz = 7.0
                out.append(PdfSpan(text=t, size=sz))
    return out


def _median_size(spans: list[PdfSpan]) -> float:
    sizes = [s.size for s in spans]
    return statistics.median(sizes) if sizes else 7.0


def _is_noise(span: PdfSpan, median: float) -> bool:
    """Exclude decorative/pure punctuation and tiny superscripts/page numbers."""
    t = (span.text or "").strip()
    if not t:
        return True
    if t and not any(c.isalnum() for c in t):
        return True
    if span.size < 6.0 and len(t) <= 2:
        return True
    # Standalone small page numbers (1-3 digits) in small font
    if re.fullmatch(r"\d{1,3}", t) and span.size < median * 0.85:
        return True
    return False


def _meaningful_spans(spans: list[PdfSpan]) -> list[PdfSpan]:
    med = _median_size(spans)
    return [s for s in spans if not _is_noise(s, med)]


def _pdf_flat(spans: list[PdfSpan]) -> str:
    return " ".join(s.text for s in spans if s.text)


def _extract_numbers(text: str) -> list[str]:
    return _NUMBER_RE.findall(text or "")


def _significant_words(spans: list[PdfSpan]) -> list[str]:
    """
    Lowercase words (len >= 5) from meaningful spans, excluding stopwords and pure-numeric tokens.
    """
    words: list[str] = []
    for span in spans:
        for token in re.split(r"[\s,;:\-/()]+", span.text or ""):
            t = token.strip(".,;:()[]{}'\"-!?").lower()
            if len(t) < 5:
                continue
            if t in _STOPWORDS:
                continue
            if re.fullmatch(r"[\d.,]+", t):
                continue
            words.append(t)
    return words


def _sections_by_page(payload: dict) -> dict[int | None, list[dict]]:
    """
    Map page number -> list of section dicts.
    Uses section['page'] when present. If no sections carry page, everything is under None.
    """
    sections = payload.get("sections") or []
    has_page = any(isinstance(s, dict) and s.get("page") is not None for s in sections)
    out: dict[int | None, list[dict]] = {}
    if not has_page:
        out[None] = [s for s in sections if isinstance(s, dict)]
        return out
    for s in sections:
        if not isinstance(s, dict):
            continue
        p = s.get("page")
        try:
            page = int(p) if p is not None else None
        except Exception:
            page = None
        out.setdefault(page, []).append(s)
    return out


def _flatten_json_sections(sections: list[dict]) -> tuple[str, list[str]]:
    """
    Return (flat_string, cell_values) from our canonical extraction JSON sections.
    """
    parts: list[str] = []
    cells: list[str] = []

    for sec in sections or []:
        if not isinstance(sec, dict):
            continue
        name = sec.get("name")
        if isinstance(name, str) and name.strip():
            parts.append(name.strip())
        for h in sec.get("headings") or []:
            if isinstance(h, str) and h.strip():
                parts.append(h.strip())
                cells.append(h.strip())
        for row in sec.get("rows") or []:
            if not isinstance(row, list):
                continue
            for cell in row:
                if cell is None:
                    continue
                v = str(cell).strip()
                if not v:
                    continue
                parts.append(v)
                cells.append(v)

    return " ".join(parts), cells


def _check_numeric(pdf_spans: list[PdfSpan], json_flat: str) -> dict:
    nums: set[str] = set()
    for span in pdf_spans:
        for n in _extract_numbers(span.text):
            digit_count = sum(c.isdigit() for c in n)
            if digit_count >= _MIN_DIGITS_TO_REPORT:
                nums.add(n)
    missing = sorted(n for n in nums if n not in (json_flat or ""))
    return {"missing_count": len(missing), "missing": missing[:250]}


def _check_text(pdf_spans: list[PdfSpan], json_flat: str) -> dict:
    json_lower = (json_flat or "").lower()
    seen: set[str] = set()
    missing: list[str] = []
    for word in _significant_words(pdf_spans):
        if word in seen:
            continue
        seen.add(word)
        if word not in json_lower:
            missing.append(word)
    return {"missing_count": len(missing), "missing": missing[:250]}


def _check_structural(sections: list[dict], meaningful_span_count: int) -> dict:
    issues: list[dict] = []

    if not sections and meaningful_span_count >= _EMPTY_PAGE_SPAN_THRESHOLD:
        issues.append(
            {
                "type": "no_sections_but_has_content",
                "meaningful_span_count": meaningful_span_count,
            }
        )
        return {"issue_count": len(issues), "issues": issues}

    for sec in sections:
        if not isinstance(sec, dict):
            continue
        sec_name = (sec.get("name") or "")[:60]
        rows = sec.get("rows") or []

        if not rows:
            issues.append({"type": "empty_section_rows", "section": sec_name})
            continue

        # Row length mismatch (treat first row as header width).
        header = rows[0] if isinstance(rows[0], list) else []
        expected = len(header)
        for i, r in enumerate(rows):
            if not isinstance(r, list):
                issues.append(
                    {"type": "row_not_a_list", "section": sec_name, "row_index": i}
                )
                continue
            if expected and len(r) != expected:
                issues.append(
                    {
                        "type": "row_length_mismatch",
                        "section": sec_name,
                        "row_index": i,
                        "expected": expected,
                        "actual": len(r),
                    }
                )

    return {"issue_count": len(issues), "issues": issues[:500]}


def _check_invented(json_cells: list[str], pdf_raw_flat: str) -> dict:
    invented: list[str] = []
    seen: set[str] = set()
    for val in json_cells:
        v = (val or "").strip()
        if not v or v in seen or v in _SYNTHETIC_VALUES:
            continue
        seen.add(v)

        if len(v) <= 3:
            pattern = r"(?<![a-zA-Z0-9])" + re.escape(v) + r"(?![a-zA-Z0-9])"
            found = bool(re.search(pattern, pdf_raw_flat or ""))
        else:
            found = v in (pdf_raw_flat or "")
        if not found:
            invented.append(v)
    return {"invented_count": len(invented), "invented": invented[:250]}


def audit_pdf_vs_extraction_json(
    pdf_path: str | Path,
    extraction_json_path: str | Path,
    *,
    max_pages: int | None = None,
) -> dict:
    """
    Audit an extraction JSON file against its source PDF.
    Returns a JSON-serializable report dict.
    """
    pdf_path = str(pdf_path)
    extraction_json_path = Path(extraction_json_path)
    payload = json.loads(extraction_json_path.read_text(encoding="utf-8"))
    by_page = _sections_by_page(payload)

    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    if max_pages is not None:
        total_pages = min(total_pages, max_pages)

    pages_numeric_gap = 0
    pages_text_gap = 0
    pages_structural = 0
    pages_invented = 0
    pages_no_sections = 0

    page_reports: list[dict] = []

    for idx in range(total_pages):
        page = doc[idx]
        page_num = idx + 1

        spans = _page_spans(page)
        m_spans = _meaningful_spans(spans)
        pdf_flat = _pdf_flat(spans)

        # Our JSON may be page-aware or not.
        json_sections = by_page.get(page_num, []) if (None not in by_page) else by_page.get(None, [])
        json_flat, json_cells = _flatten_json_sections(json_sections)

        # Shortcut: no PDF content and no JSON content → skip
        if not m_spans and not json_cells:
            continue

        r_numeric = _check_numeric(m_spans, json_flat)
        r_text = _check_text(m_spans, json_flat)
        r_structural = _check_structural(json_sections, len(m_spans))
        r_invented = _check_invented(json_cells, pdf_flat)

        if r_numeric["missing_count"] > 0:
            pages_numeric_gap += 1
        if r_text["missing_count"] > 0:
            pages_text_gap += 1
        if r_structural["issue_count"] > 0:
            pages_structural += 1
        if r_invented["invented_count"] > 0:
            pages_invented += 1
        if any(i.get("type") == "no_sections_but_has_content" for i in r_structural.get("issues", [])):
            pages_no_sections += 1

        has_issue = (
            r_numeric["missing_count"] > 0
            or r_text["missing_count"] > 0
            or r_structural["issue_count"] > 0
            or r_invented["invented_count"] > 0
        )

        page_reports.append(
            {
                "page": page_num,
                "meaningful_span_count": len(m_spans),
                "json_section_count": len(json_sections),
                "has_issue": bool(has_issue),
                "check_numeric_coverage": r_numeric,
                "check_text_coverage": r_text,
                "check_structural": r_structural,
                "check_invented_values": r_invented,
            }
        )

    return {
        "source_pdf": pdf_path,
        "source_json": str(extraction_json_path),
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "total_pdf_pages": doc.page_count,
        "pages": page_reports,
        "summary": {
            "pages_audited": len(page_reports),
            "pages_with_numeric_gaps": pages_numeric_gap,
            "pages_with_text_gaps": pages_text_gap,
            "pages_with_structural_issues": pages_structural,
            "pages_with_invented_values": pages_invented,
            "pages_no_sections_but_content": pages_no_sections,
        },
    }


def apply_audit_to_extraction_file(
    pdf_path: str | Path,
    extraction_json_path: str | Path,
    *,
    audit_pages: int | None = 3,
    strict: bool = False,
    report_path: str | Path | None = None,
    silent: bool = False,
) -> tuple[dict, bool]:
    """
    Run PDF-vs-JSON audit, merge summary into extraction JSON meta, optional full report file.

    Returns (audit_report, ok). ok=True when numeric gaps, invented values, and no-sections are all zero
    within audited pages.

    If audit_pages <= 0, skips audit and returns ({}, True).
    If silent=True, do not print to stderr (use from web servers).
    """
    pdf_path = Path(pdf_path)
    extraction_json_path = Path(extraction_json_path)
    report_path = Path(report_path) if report_path else None

    if audit_pages is not None and audit_pages <= 0:
        return {}, True

    report = audit_pdf_vs_extraction_json(pdf_path, extraction_json_path, max_pages=audit_pages)
    summary = report.get("summary") or {}

    numeric_gaps = int(summary.get("pages_with_numeric_gaps") or 0)
    no_sections = int(summary.get("pages_no_sections_but_content") or 0)
    invented = int(summary.get("pages_with_invented_values") or 0)
    structural = int(summary.get("pages_with_structural_issues") or 0)
    text_gaps = int(summary.get("pages_with_text_gaps") or 0)

    ok = (numeric_gaps == 0) and (no_sections == 0) and (invented == 0)

    try:
        payload = json.loads(extraction_json_path.read_text(encoding="utf-8"))
        meta = payload.get("meta") if isinstance(payload, dict) else None
        if not isinstance(meta, dict):
            meta = {}
        meta["audit_summary"] = {
            "audit_pages": audit_pages,
            "pages_audited": int(summary.get("pages_audited") or 0),
            "pages_with_numeric_gaps": numeric_gaps,
            "pages_with_text_gaps": text_gaps,
            "pages_with_structural_issues": structural,
            "pages_with_invented_values": invented,
            "pages_no_sections_but_content": no_sections,
            "passed": bool(ok),
        }
        if not ok:
            meta["requires_review"] = True
            cur = (meta.get("status") or "").strip().lower()
            if cur != "failed":
                meta["status"] = "requires_review"
        payload["meta"] = meta
        extraction_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if not silent:
        if ok:
            print("Audit: PASS (no missing numbers / no invented values).", file=sys.stderr)
        else:
            print(
                "Audit: REVIEW REQUIRED "
                f"(numeric_gaps_pages={numeric_gaps}, invented_values_pages={invented}, no_sections_pages={no_sections}).",
                file=sys.stderr,
            )
            if strict:
                print("Error: Extraction audit failed (strict mode).", file=sys.stderr)

    return report, ok

