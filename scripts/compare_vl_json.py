#!/usr/bin/env python3
"""
Compare two VL extraction JSON files (e.g. statement.json vs statement2.json).
Prints a summary diff: section names, row counts, and optional cell-level differences.

Usage:
  python scripts/compare_vl_json.py path/to/a.json path/to/b.json
  python scripts/compare_vl_json.py a.json b.json --brief   # section/row summary only
  python scripts/compare_vl_json.py a.json b.json --verbose  # include first few cell diffs per section
"""

import argparse
import json
import sys
from pathlib import Path
from decimal import Decimal

from tables_to_excel import _cell_value


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sections_from_payload(payload: dict) -> list[dict]:
    return payload.get("sections") or []


def section_key(sec: dict, index: int) -> str:
    name = (sec.get("name") or "").strip()
    page = sec.get("page")
    if page is not None:
        return f"{name} (p{page})"
    return f"{name}[{index}]"


def compare(
    a_path: Path,
    b_path: Path,
    brief: bool = False,
    verbose: bool = False,
    *,
    numeric_tol: float = 0.01,
) -> None:
    a_payload = load_json(a_path)
    b_payload = load_json(b_path)
    a_sections = sections_from_payload(a_payload)
    b_sections = sections_from_payload(b_payload)

    a_meta = a_payload.get("meta") or {}
    b_meta = b_payload.get("meta") or {}

    print(f"File A: {a_path.name}  ({len(a_sections)} sections)")
    print(f"File B: {b_path.name}  ({len(b_sections)} sections)")
    if a_meta or b_meta:
        if a_meta.get("vl_timing_seconds") is not None:
            print(f"  A timing: {a_meta.get('vl_timing_seconds')} s total, pages: {a_meta.get('pages_processed', [])}")
        if b_meta.get("vl_timing_seconds") is not None:
            print(f"  B timing: {b_meta.get('vl_timing_seconds')} s total, pages: {b_meta.get('pages_processed', [])}")
    print()

    # Build simple keys for alignment: by (name, page) and index
    def summarize(sec: dict) -> dict:
        return {
            "name": (sec.get("name") or "").strip(),
            "page": sec.get("page"),
            "row_count": sec.get("row_count") or len(sec.get("rows") or []),
            "column_count": sec.get("column_count") or (len((sec.get("rows") or [{}])[0]) if sec.get("rows") else 0),
            "headings": sec.get("headings") or [],
            "rows": sec.get("rows") or [],
        }

    a_sum = [summarize(s) for s in a_sections]
    b_sum = [summarize(s) for s in b_sections]

    # Section count diff
    if len(a_sum) != len(b_sum):
        print(f"Section count: A={len(a_sum)}  B={len(b_sum)}  (diff: {len(b_sum) - len(a_sum):+d})")
    else:
        print(f"Section count: {len(a_sum)} (same)")

    # Per-section comparison (by index)
    max_idx = max(len(a_sum), len(b_sum))
    has_diff = False
    for i in range(max_idx):
        sa = a_sum[i] if i < len(a_sum) else None
        sb = b_sum[i] if i < len(b_sum) else None
        key_a = section_key(a_sections[i], i) if i < len(a_sections) else f"[{i}]"
        key_b = section_key(b_sections[i], i) if i < len(b_sections) else f"[{i}]"
        label = key_a if sa else key_b
        if sa is None:
            print(f"  [{i}] {label}: only in B (rows={sb['row_count']}, cols={sb['column_count']})")
            has_diff = True
            continue
        if sb is None:
            print(f"  [{i}] {label}: only in A (rows={sa['row_count']}, cols={sa['column_count']})")
            has_diff = True
            continue
        rc_a, rc_b = sa["row_count"], sb["row_count"]
        cc_a, cc_b = sa["column_count"], sb["column_count"]
        if rc_a != rc_b or cc_a != cc_b:
            print(f"  [{i}] {label}: rows {rc_a} vs {rc_b}, cols {cc_a} vs {cc_b}")
            has_diff = True
        else:
            # Same shape: compute mismatch ratio (ignoring cells that are blank in both).
            rows_a, rows_b = sa["rows"], sb["rows"]

            tol = Decimal(str(numeric_tol))

            def norm(c):
                v = _cell_value(c)
                if v == "":
                    return None
                if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
                    return ("num", Decimal(str(v)))
                return ("str", str(v).strip())

            def eq_cell(a, b) -> bool:
                na, nb = norm(a), norm(b)
                if na is None and nb is None:
                    return True
                if na is None or nb is None:
                    return False
                if na[0] == "num" and nb[0] == "num":
                    try:
                        return abs(na[1] - nb[1]) <= tol
                    except Exception:
                        return False
                if na[0] != nb[0]:
                    return False
                return na[1] == nb[1]

            compared = 0
            mismatched = 0
            sample_diffs: list[tuple[int, int, str, str]] = []

            for ri, (ra, rb) in enumerate(zip(rows_a, rows_b)):
                for ci, (ca, cb) in enumerate(zip(ra, rb)):
                    na, nb = norm(ca), norm(cb)
                    if na is None and nb is None:
                        continue
                    compared += 1
                    if not eq_cell(ca, cb):
                        mismatched += 1
                        if verbose and not brief and len(sample_diffs) < 5:
                            sample_diffs.append((ri, ci, str(ca)[:30], str(cb)[:30]))

            if mismatched:
                ratio = mismatched / max(1, compared)
                has_diff = True
                if not brief:
                    print(f"  [{i}] {label}: cell mismatches {mismatched}/{compared} (ratio={ratio:.3%})")
                    if verbose and not brief and sample_diffs:
                        print(f"  [{i}] {label}: cell diffs (sample):")
                        for ri, ci, ca, cb in sample_diffs[:5]:
                            print(f"    row {ri} col {ci}: {repr(ca)} vs {repr(cb)}")

    if not has_diff:
        print("Sections: structure and row/column counts match.")
        if not brief:
            for i in range(min(len(a_sum), len(b_sum))):
                if a_sum[i]["rows"] != b_sum[i]["rows"]:
                    print(f"  [{i}] {section_key(a_sections[i], i)}: same shape but cell values differ")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare two VL extraction JSON files")
    ap.add_argument("json_a", type=Path, help="First JSON file")
    ap.add_argument("json_b", type=Path, help="Second JSON file")
    ap.add_argument("--brief", action="store_true", help="Only section/row count summary")
    ap.add_argument("--verbose", "-v", action="store_true", help="Show sample cell-level diffs")
    ap.add_argument("--numeric-tol", type=float, default=0.01, help="Numeric tolerance for cell comparison")
    args = ap.parse_args()
    if not args.json_a.exists():
        print(f"Error: not found: {args.json_a}", file=sys.stderr)
        return 1
    if not args.json_b.exists():
        print(f"Error: not found: {args.json_b}", file=sys.stderr)
        return 1
    compare(args.json_a, args.json_b, brief=args.brief, verbose=args.verbose, numeric_tol=args.numeric_tol)
    return 0


if __name__ == "__main__":
    sys.exit(main())
