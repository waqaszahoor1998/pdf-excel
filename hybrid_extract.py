#!/usr/bin/env python3
"""
Hybrid extraction: library (pdfplumber/PyMuPDF) first, then VL only on "bad" pages.

Flow:
  1. Extract all pages with the library (tables_to_excel.extract_sections_from_pdf).
  2. Detect "bad" pages: pages where no section looks like a real table (too few cells,
     no multi-column rows, or only junk text).
  3. If there are bad pages, run the vision-language model only on those page numbers.
  4. Merge: keep library sections for good pages; replace bad-page content with VL sections.
  5. Write canonical JSON (sections + meta). Meta includes per-page VL timing when VL was used.

Usage:
  python run.py hybrid <pdf> --schema-type broker_statement -o output/statement_hybrid.json
  python run.py from-json output/statement_hybrid.json -o output/statement_hybrid.xlsx

See docs/hybrid.md for a full description of how the hybrid system works.
"""

import json
import logging
import re
from pathlib import Path

from tables_to_excel import (
    extract_sections_from_pdf,
    filter_sections_to_tables_only,
    _looks_like_table,
    _sections_to_json_serializable,
    refine_json_sections,
)

log = logging.getLogger(__name__)


def _should_force_universal_prompt(pdf_path: Path) -> bool:
    """
    For some broker-like PDFs (e.g. JPM Combined/Consolidated statements), the strict
    broker prompt over-constrains columns and can reorder headings. Detect these layouts
    and use the universal prompt for VL pages.
    """
    try:
        import fitz
    except Exception:
        return False
    try:
        doc = fitz.open(str(pdf_path))
        max_pages = min(8, len(doc))
        blob = []
        for i in range(max_pages):
            blob.append(doc[i].get_text("text") or "")
        text = "\n".join(blob).lower()
    except Exception:
        return False

    has_consolidated = "consolidated statement" in text or "consolidated summary" in text
    has_account_summary = "account summary" in text
    has_portfolio_activity = "portfolio activity" in text
    # Strongly indicates this JPM combined-style layout.
    return has_consolidated and has_account_summary and has_portfolio_activity


def _split_bad_pages_for_prompt_mix(pdf_path: Path, bad_pages: list[int]) -> tuple[list[int], list[int]]:
    """
    For consolidated-style broker statements, not all routed pages should use the same prompt.
    Returns (universal_pages, broker_pages).
    """
    try:
        import fitz
    except Exception:
        return bad_pages, []
    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return bad_pages, []

    universal_keywords = [
        "account summary",
        "consolidated summary",
        "portfolio activity",
        "tax summary",
        "asset allocation",
        "investment accounts",
        "cash & fixed income summary",
    ]
    broker_keywords = [
        "cash & fixed income detail",
        "portfolio activity detail",
        "transactions",
        "inflows and outflows",
        "us fixed income",
        "equity detail",
        "summary by type",
        "summary by maturity",
        "assets category",
    ]

    universal_pages: list[int] = []
    broker_pages: list[int] = []
    for p in bad_pages:
        if p < 1 or p > len(doc):
            broker_pages.append(p)
            continue
        text = (doc[p - 1].get_text("text") or "").lower()
        u_hits = sum(1 for k in universal_keywords if k in text)
        b_hits = sum(1 for k in broker_keywords if k in text)
        # Tie-break toward universal for summary pages.
        if u_hits >= b_hits:
            universal_pages.append(p)
        else:
            broker_pages.append(p)
    return universal_pages, broker_pages


def _page_quality(page_sections: list[tuple]) -> tuple[float, list[str]]:
    """
    Compute a quality score in [0, 1] for one page using library-extracted sections.
    Lower score means the page likely needs VL re-extraction.
    """
    if not page_sections:
        return 0.0, ["no_sections"]

    table_like_count = 0
    structured_count = 0
    null_heavy_count = 0
    suspicious_name_count = 0
    long_text_rows = 0
    total_rows = 0

    for s in page_sections:
        sec_name = (s[0] or "").strip()
        heading_rows = s[1] or []
        data_rows = s[2] or []

        if _looks_like_table(sec_name, heading_rows, data_rows):
            table_like_count += 1

        if re.search(r"(_\d+$|12125|to\s+12_1)", sec_name, re.I):
            suspicious_name_count += 1

        max_row_cells = 0
        nonempty_cells = 0
        total_cells = 0
        for r in data_rows:
            row = r if isinstance(r, (list, tuple)) else [r]
            row_nonempty = len([c for c in row if c is not None and str(c).strip()])
            max_row_cells = max(max_row_cells, row_nonempty)
            total_cells += len(row)
            nonempty_cells += row_nonempty
            total_rows += 1
            if any(c is not None and len(str(c).strip()) > 100 for c in row):
                long_text_rows += 1

        fill_ratio = (nonempty_cells / total_cells) if total_cells else 0.0
        if fill_ratio < 0.5:
            null_heavy_count += 1
        if len(data_rows) >= 3 and max_row_cells >= 3:
            structured_count += 1

    n = len(page_sections)
    table_like_ratio = table_like_count / n
    structured_ratio = structured_count / n
    null_heavy_ratio = null_heavy_count / n
    suspicious_name_ratio = suspicious_name_count / n
    long_text_ratio = (long_text_rows / total_rows) if total_rows else 0.0

    score = (
        0.45 * table_like_ratio
        + 0.25 * (1.0 - null_heavy_ratio)
        + 0.20 * structured_ratio
        + 0.10 * (1.0 - suspicious_name_ratio)
    )
    score = max(0.0, min(1.0, score))

    reasons: list[str] = []
    if table_like_ratio < 0.5:
        reasons.append("low_table_like_ratio")
    if null_heavy_ratio > 0.4:
        reasons.append("null_heavy")
    if structured_ratio < 0.4:
        reasons.append("weak_structure")
    if suspicious_name_ratio > 0.4:
        reasons.append("suspicious_section_names")
    if long_text_ratio > 0.3:
        reasons.append("prose_mixed_rows")
    if not reasons:
        reasons.append("quality_ok")
    return round(score, 4), reasons


def _dict_sections_to_tuples(section_dicts: list[dict]) -> list[tuple]:
    """
    Convert canonical section dicts (from VL) to tuple form used by quality scorer:
    (name, headings, rows, page)
    """
    out = []
    for s in section_dicts or []:
        out.append((
            s.get("name", "") or "",
            s.get("headings", []) or [],
            s.get("rows", []) or [],
            s.get("page"),
        ))
    return out


def _suspicious_name_ratio(page_sections: list[tuple]) -> float:
    if not page_sections:
        return 0.0
    bad = 0
    for s in page_sections:
        sec_name = (s[0] or "").strip()
        if re.search(r"(_\d+$|12125|to\s+12_1)", sec_name, re.I):
            bad += 1
    return bad / len(page_sections)


def detect_bad_pages(sections: list[tuple], quality_threshold: float = 0.72) -> tuple[list[int], dict[int, dict]]:
    """
    Decide which pages need VL re-extraction. A page is "bad" if it has no section
    that looks like a real table (multi-column, structured data). Such pages are
    often scanned, image-heavy, or layout-heavy and benefit from the vision model.
    """
    # Group sections by page (1-based)
    from collections import defaultdict
    by_page = defaultdict(list)
    for s in sections:
        page_num = s[3] if len(s) >= 4 else None
        if page_num is not None:
            by_page[page_num].append(s)
    bad = []
    diagnostics: dict[int, dict] = {}
    for page_num, page_sections in sorted(by_page.items()):
        has_table = any(_looks_like_table(s[0], s[1], s[2]) for s in page_sections)
        quality_score, reasons = _page_quality(page_sections)
        severe_combo = (
            ("suspicious_section_names" in reasons and "null_heavy" in reasons)
            or ("suspicious_section_names" in reasons and "weak_structure" in reasons)
            or ("null_heavy" in reasons and "weak_structure" in reasons)
        )
        route_to_vl = (not has_table) or (quality_score < quality_threshold) or severe_combo
        diagnostics[page_num] = {
            "quality_score": quality_score,
            "has_table_like_section": bool(has_table),
            "route_to_vl": bool(route_to_vl),
            "severe_combo": bool(severe_combo),
            "reasons": reasons,
        }
        if route_to_vl:
            bad.append(page_num)
    return sorted(bad), diagnostics


def hybrid_pdf_to_json(
    pdf_path: str | Path,
    output_path: str | Path,
    schema_type: str | None = None,
    max_pages: int | None = None,
    overwrite: bool = True,
) -> str:
    """
    Extract PDF with hybrid (library + VL on bad pages). Writes canonical JSON
    with sections and meta. Meta includes:
      - hybrid: true
      - hybrid_bad_pages: list of 1-based page numbers that were re-run with VL
      - vl_timing_seconds: total VL inference time (seconds)
      - vl_per_page_seconds: list of seconds per VL page (same order as vl_page_numbers)
      - vl_page_numbers: list of page numbers sent to VL
      - vl_page_timings: list of { "page": N, "seconds": S } for per-page timing
    """
    pdf_path = Path(pdf_path)
    output_path = Path(output_path)
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Output exists: {output_path} (use overwrite=True)")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1) Library extraction (optionally first N pages only)
    log.info("Hybrid: library extraction on %s", pdf_path.name)
    raw_library_sections = extract_sections_from_pdf(str(pdf_path), max_pages=max_pages)
    bad_pages, routing = detect_bad_pages(raw_library_sections)
    library_sections = filter_sections_to_tables_only(raw_library_sections)
    log.info("Hybrid: detected %d bad page(s): %s", len(bad_pages), bad_pages)

    if max_pages is not None:
        bad_pages = [p for p in bad_pages if p <= max_pages]
        routing = {k: v for k, v in routing.items() if k <= max_pages}

    meta = {
        "pdf_name": pdf_path.name,
        "pdf_path": str(pdf_path.resolve()),
        "hybrid": True,
        "hybrid_max_pages": max_pages,
        "hybrid_bad_pages": bad_pages,
        "hybrid_page_routing": {str(k): v for k, v in sorted(routing.items())},
        "hybrid_quality_threshold": 0.72,
    }

    if not bad_pages:
        # No VL: write library-only JSON
        section_dicts = refine_json_sections(_sections_to_json_serializable(library_sections))
        payload = {"sections": section_dicts, "meta": meta}
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        log.info("Hybrid: no bad pages; wrote library-only JSON to %s", output_path)
        return str(output_path)

    # 2) VL only on bad pages
    from extract_vl import (
        extract_pdf_with_vl,
        _vl_text_to_sections,
        _normalize_sections,
        _drop_repetitive_sections,
        _split_performance_sections,
        _clear_duplicate_data_in_consecutive_rows,
        _get_prompt_for_schema,
    )
    # Title-agnostic default: use universal prompt unless caller explicitly chooses schema_type.
    if schema_type:
        prompt = _get_prompt_for_schema(schema_type)
        meta["detected_document_type"] = schema_type
    else:
        prompt = _get_prompt_for_schema("universal")
        meta["detected_document_type"] = "universal"

    text, vl_meta = extract_pdf_with_vl(
        pdf_path,
        prompt=prompt,
        max_pages=max_pages,
        page_ranges=bad_pages,
    )
    vl_sections = _vl_text_to_sections(text)

    vl_sections = _normalize_sections(vl_sections)
    vl_sections = _drop_repetitive_sections(vl_sections)
    vl_sections = _split_performance_sections(vl_sections)
    vl_sections = _clear_duplicate_data_in_consecutive_rows(vl_sections)

    # 3) Per-page timing in meta
    meta["vl_timing_seconds"] = vl_meta.get("total_seconds")
    meta["vl_per_page_seconds"] = vl_meta.get("per_page_seconds", [])
    meta["vl_page_numbers"] = vl_meta.get("page_numbers", [])
    meta["vl_page_timings"] = [
        {"page": p, "seconds": round(s, 2)}
        for p, s in zip(
            vl_meta.get("page_numbers", []),
            vl_meta.get("per_page_seconds", []),
        )
    ]
    if vl_meta.get("total_seconds") is not None:
        log.info(
            "Hybrid: VL timing total %.1f s, per-page %s",
            vl_meta["total_seconds"],
            meta["vl_page_timings"],
        )

    # 4) Per-page winner selection for routed pages:
    #    if VL page quality is weaker than library quality, keep library page instead.
    from collections import defaultdict
    lib_by_page = defaultdict(list)
    for s in raw_library_sections:
        page_num = s[3] if len(s) >= 4 else None
        if page_num is not None:
            lib_by_page[page_num].append(s)
    vl_by_page = defaultdict(list)
    for s in _dict_sections_to_tuples(vl_sections):
        page_num = s[3] if len(s) >= 4 else None
        if page_num is not None:
            vl_by_page[page_num].append(s)

    selected_source_by_page: dict[int, str] = {}
    page_quality_compare: dict[int, dict] = {}
    effective_bad_pages: list[int] = []
    fallback_pages: list[int] = []
    for page_num in bad_pages:
        lib_page_sections = lib_by_page.get(page_num, [])
        vl_page_sections = vl_by_page.get(page_num, [])
        lib_q, _ = _page_quality(lib_page_sections)
        vl_q, _ = _page_quality(vl_page_sections)
        lib_susp_ratio = _suspicious_name_ratio(lib_page_sections)
        vl_susp_ratio = _suspicious_name_ratio(vl_page_sections)

        # Keep library if it's clearly better on this routed page.
        # Guardrail: if library names are mostly suspicious but VL names are cleaner,
        # prefer VL even when lib_q is numerically close.
        library_names_look_bad = lib_susp_ratio >= 0.6
        vl_names_look_cleaner = vl_susp_ratio <= 0.4
        use_library = (
            lib_q >= 0.55
            and lib_q > vl_q + 0.08
            and not (library_names_look_bad and vl_names_look_cleaner)
        )
        if use_library:
            selected_source_by_page[page_num] = "library_fallback"
            fallback_pages.append(page_num)
        else:
            selected_source_by_page[page_num] = "vl"
            effective_bad_pages.append(page_num)
        page_quality_compare[page_num] = {
            "library_quality": lib_q,
            "vl_quality": vl_q,
            "library_suspicious_name_ratio": round(lib_susp_ratio, 4),
            "vl_suspicious_name_ratio": round(vl_susp_ratio, 4),
            "selected": selected_source_by_page[page_num],
        }

    meta["hybrid_selected_source_by_page"] = {str(k): v for k, v in sorted(selected_source_by_page.items())}
    meta["hybrid_page_quality_compare"] = {str(k): v for k, v in sorted(page_quality_compare.items())}
    meta["hybrid_library_fallback_pages"] = fallback_pages

    # 5) Merge: library sections for good pages + fallback pages, VL sections for effective bad pages
    bad_set = set(bad_pages)
    effective_bad_set = set(effective_bad_pages)
    library_dicts = _sections_to_json_serializable([
        s for s in library_sections
        if len(s) < 4 or s[3] is None or s[3] not in effective_bad_set
    ])
    # VL sections are already dicts with "page"
    vl_kept = [s for s in vl_sections if s.get("page") in effective_bad_set]
    merged = library_dicts + vl_kept
    # Sort by page then by original order (library first per page, then VL)
    def sort_key(sec):
        page = sec.get("page")
        return (page if page is not None else 0, id(sec))
    merged.sort(key=sort_key)

    payload = {"sections": refine_json_sections(merged), "meta": meta}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    log.info(
        "Hybrid: wrote %d sections to %s (VL used for pages %s; library fallback pages %s)",
        len(merged),
        output_path,
        effective_bad_pages,
        fallback_pages,
    )
    return str(output_path)
