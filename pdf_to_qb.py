#!/usr/bin/env python3
"""
Transform extracted PDF tables into QB Automation Sheet format.

Pipeline: PDF → (tables_to_excel) → raw xlsx → (this module) → QB-format xlsx.

- Groups sheets by target name (e.g. all "Asset Allocation" into one sheet).
- Uses standard QB-style sheet names (see EXPECTED_FORMAT.md).
- Preserves table structure; merges duplicate section types into one sheet per type.
"""

import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

# QB-style colors (from sample workbook – see color scan below)
# GREEN 92D050: section separator row; first row of each block; cells that contain account IDs (902-7, 1004, E79271004)
# YELLOW FFFF00: formula cells (=SUM(...)) and "Checks" label
# ORANGE FFC000: emphasis (e.g. Net Assets subtotal area)
FILL_SECTION_HEADER = PatternFill(fill_type="solid", fgColor="92D050")   # Light green
FILL_TABLE_HEADER = PatternFill(fill_type="solid", fgColor="D9E1F2")    # Light blue – column header row
FILL_FORMULA = PatternFill(fill_type="solid", fgColor="FFFF00")         # Yellow – formulas / check cells
FILL_TOTALS = PatternFill(fill_type="solid", fgColor="FFC000")          # Orange – totals / emphasis

# Target sheet names we want in QB format (order for creation)
QB_SHEET_ORDER = [
    "Period Summary",
    "Account Summary",
    "Consolidated Summary",
    "Asset Allocation",
    "Portfolio Activity",
    "Tax Summary",
    "Cash & Fixed Income",
    "Equity Summary",
    "Equity Detail",
    "Net Assets",
    "Operations",
    "Partner Capital",
    "PLSummary",
    "Journal Entry Import",
    "Journal Entries",
    "Unrealized",
    "Change in Dividend",
    "Change in Interest",
    "Alt Inv Transfer",
]


def _target_sheet_name(source_name: str) -> str:
    """Map extracted sheet name to QB target sheet name (for grouping)."""
    s = (source_name or "").strip()
    if not s:
        return "Other"
    # Strip trailing " 2", " 3", "_1", "_11" etc.
    base = re.sub(r"\s+\d+$", "", s)
    base = re.sub(r"_\d+$", "", base)
    # If base is a known QB name, use it
    if base in QB_SHEET_ORDER:
        return base
    # Per-account pattern: "ABC TRUST ACCT. E79271004_1" -> "Account E79271004" (merge all pages for same account)
    m = re.search(r"ACCT\.\s*([A-Z0-9]+)", s, re.I)
    if m:
        return f"Account {m.group(1)}"
    # JPMorgan / broker header as sheet name -> "Broker Info"
    if "JPMorgan" in s or "J.P. Morgan" in s or "Chase Bank" in s:
        return "Broker Info"
    return base or s


def _rows_from_sheet(ws) -> list[list]:
    """Read all rows from a worksheet as list of lists (cell values)."""
    return [list(row) for row in ws.iter_rows(values_only=True)]


def _safe_sheet_name(name: str, max_len: int = 31) -> str:
    """Excel sheet name: no \\ / * ? [ ]"""
    s = (name or "Sheet").replace("\\", "").replace("/", "").replace("*", "").replace("?", "").replace("[", "").replace("]", "")
    return (s[:max_len] if s else "Sheet").strip() or "Sheet"


def _fill_row(ws, row: int, num_cols: int, fill: PatternFill) -> None:
    """Apply a fill to columns 1 through num_cols in the given row."""
    if fill is None:
        return
    for c in range(1, num_cols + 1):
        ws.cell(row=row, column=c).fill = fill


def _looks_like_header_row(row: list) -> bool:
    """True if row looks like a table header (short text, no big numbers)."""
    if not row:
        return False
    cells = [str(c).strip() for c in (row if isinstance(row, (list, tuple)) else [row]) if c is not None]
    if len(cells) < 2:
        return False
    header_like = ("account", "market", "value", "bom", "eom", "mtd", "cash", "number", "date", "description", "debit", "credit")
    return any(h in " ".join(cells).lower() for h in header_like)


def _is_account_id(val) -> bool:
    """True if value looks like an account ID (e.g. 902-7, 1004, E79271004, 9511)."""
    if val is None:
        return False
    s = str(val).strip()
    if not s or len(s) > 20:
        return False
    # Digits with optional dash and digits (902-7, 1004, 9511)
    if re.match(r"^\d{3,}(-\d+)?$", s):
        return True
    # Alphanumeric like E79271004, G41269004
    if re.match(r"^[A-Z]?\d{6,}$", s, re.I):
        return True
    return False


def _is_formula_or_check(val) -> bool:
    """True if cell is a formula or 'Checks' label (yellow in sample)."""
    if val is None:
        return False
    s = str(val).strip()
    return s.startswith("=") or s.lower() == "checks"


def _is_totals_row(row: list) -> bool:
    """True if first cell looks like a Totals row."""
    if not row:
        return False
    first = (row[0] if isinstance(row, (list, tuple)) else row)
    s = (str(first).strip().lower() if first is not None else "")
    return s in ("total", "totals", "total value", "total assets", "total liabilities")


def transform_extracted_to_qb(extracted_xlsx_path: str, output_path: str) -> str:
    """
    Read an extracted workbook (from pdf_tables_to_excel) and write a QB-format workbook.

    - Groups sheets by target name (e.g. all Asset Allocation → one sheet).
    - Writes sections one after another with a blank row and section title between.
    - Returns the path to the written file.
    """
    from openpyxl import load_workbook

    in_path = Path(extracted_xlsx_path)
    out_path = Path(output_path)
    if not in_path.exists():
        raise FileNotFoundError(f"Extracted file not found: {in_path}")

    wb_in = load_workbook(in_path, read_only=True, data_only=True)
    # Collect: target_name -> [(source_sheet_name, rows), ...]
    by_target: dict[str, list[tuple[str, list[list]]]] = {}

    for sheet_name in wb_in.sheetnames:
        ws = wb_in[sheet_name]
        rows = _rows_from_sheet(ws)
        if not rows:
            continue
        target = _target_sheet_name(sheet_name)
        by_target.setdefault(target, []).append((sheet_name, rows))
    wb_in.close()

    # Build ordered list of (target_name, blocks)
    seen = set()
    ordered_targets = []
    for name in QB_SHEET_ORDER:
        if name in by_target and name not in seen:
            ordered_targets.append(name)
            seen.add(name)
    for name in sorted(by_target.keys()):
        if name not in seen:
            ordered_targets.append(name)
            seen.add(name)

    wb_out = Workbook()
    wb_out.remove(wb_out.active)

    for target_name in ordered_targets:
        blocks = by_target[target_name]
        safe_name = _safe_sheet_name(target_name)
        ws = wb_out.create_sheet(title=safe_name)
        row_num = 1
        for i, (source_name, rows) in enumerate(blocks):
            if i > 0:
                # Section separator: light green bar so blocks are visually distinct
                cell = ws.cell(row=row_num, column=1, value=f"— {source_name} —")
                cell.font = Font(italic=True)
                _fill_row(ws, row_num, 20, FILL_SECTION_HEADER)  # fill across 20 cols for visibility
                row_num += 1
                row_num += 1  # blank
            for row_idx, r in enumerate(rows):
                r_list = r if r else []
                num_cols = max(len(r_list), 1)
                for col_idx, val in enumerate(r_list, start=1):
                    cell = ws.cell(row=row_num, column=col_idx, value=val)
                    # Per-cell colors (from sample): formula/Checks -> yellow; account ID -> green
                    if _is_formula_or_check(val):
                        cell.fill = FILL_FORMULA
                    elif _is_account_id(val):
                        cell.fill = FILL_SECTION_HEADER
                # Row-level colors: section title row; header row; totals row
                if row_idx == 0:
                    _fill_row(ws, row_num, num_cols, FILL_SECTION_HEADER)
                elif row_idx == 1 and _looks_like_header_row(r_list):
                    _fill_row(ws, row_num, num_cols, FILL_TABLE_HEADER)
                elif _is_totals_row(r_list):
                    _fill_row(ws, row_num, num_cols, FILL_TOTALS)
                row_num += 1
            row_num += 1  # blank after each block

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb_out.save(out_path)
    return str(out_path)


def pdf_to_qb_excel(pdf_path: str, output_path: str, overwrite: bool = True) -> str:
    """
    Full pipeline: extract PDF to Excel, then transform to QB format.

    1. Run tables_to_excel to a temp file.
    2. Transform that file to QB layout (merge/rename sheets).
    3. Save to output_path. Returns output_path.
    """
    import tempfile
    from tables_to_excel import pdf_tables_to_excel

    out_path = Path(output_path)
    if out_path.exists() and not overwrite:
        raise FileExistsError(f"Output exists: {out_path}")

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        temp_extracted = f.name
    try:
        pdf_tables_to_excel(pdf_path, temp_extracted, overwrite=True)
        transform_extracted_to_qb(temp_extracted, output_path)
        return str(out_path)
    finally:
        Path(temp_extracted).unlink(missing_ok=True)
