#!/usr/bin/env python3
"""
PDF → Excel (no AI). Extract all tables from a PDF and write them to an Excel file.

Part of the converter foundation. Use extract.py for the AI agent (natural-language extraction).
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

import pdfplumber
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter


def _safe_sheet_name(name: str, fallback: int) -> str:
    """Excel sheet names: max 31 chars, no \\ / * ? [ ]"""
    s = (name or f"Sheet{fallback}").replace("\\", "").replace("/", "").replace("*", "").replace("?", "").replace("[", "").replace("]", "")
    return s[:31] if s else f"Sheet{fallback}"


# Max vertical gap (pt) to consider text as "heading above" a table
HEADING_GAP_PT = 35
# Min vertical gap (pt) between text blocks to start a new section when no grid tables
SECTION_GAP_PT = 18

# Table detection: "text" strategy finds tables without explicit grid lines (e.g. bank statements)
TABLE_SETTINGS = {"vertical_strategy": "text", "horizontal_strategy": "text"}

# Section title patterns to split one big table into sub-tables (e.g. Asset Allocation, Portfolio Activity, Tax Summary)
SECTION_TITLE_PATTERNS = re.compile(
    r"^(Asset\s+Allocation|Portfolio\s+Activity|Tax\s+Summary|Account\s+Summary)$",
    re.IGNORECASE,
)

# Map PDF report/section titles to target sheet names (see EXPECTED_FORMAT.md).
# Order matters: more specific patterns first. Includes broker combined-statement sections (e.g. 9004 PDF).
REPORT_TITLE_TO_SHEET = [
    # Fund-accounting / QB Automation target names
    (re.compile(r"statement\s+of\s+net\s+assets", re.I), "Net Assets"),
    (re.compile(r"statement\s+of\s+operations", re.I), "Operations"),
    (re.compile(r"change\s+in\s+partners['\u2019]?\s*capital", re.I), "Partner Capital"),
    (re.compile(r"mtd\s+pnl\s+per\s+trading\s+account\s+summary", re.I), "PLSummary"),
    (re.compile(r"journal\s+entry\s+import", re.I), "Journal Entry Import"),
    (re.compile(r"journal\s+entries?", re.I), "Journal Entries"),
    (re.compile(r"unrealized\s+gains?\s+and\s+losses?", re.I), "Unrealized"),
    (re.compile(r"changes?\s+in\s+accrued\s+dividend", re.I), "Change in Dividend"),
    (re.compile(r"changes?\s+in\s+accrued\s+interest", re.I), "Change in Interest"),
    (re.compile(r"alt\s+inv\s+transfer", re.I), "Alt Inv Transfer"),
    # Broker combined-statement sections (e.g. JPM 9004-20251231-Combined-Statement)
    (re.compile(r"consolidated\s+summary", re.I), "Consolidated Summary"),
    (re.compile(r"account\s+summary", re.I), "Account Summary"),
    (re.compile(r"for\s+the\s+period", re.I), "Period Summary"),
    (re.compile(r"asset\s+allocation", re.I), "Asset Allocation"),
    (re.compile(r"portfolio\s+activity", re.I), "Portfolio Activity"),
    (re.compile(r"tax\s+summary", re.I), "Tax Summary"),
    (re.compile(r"cash\s+[&]\s+fixed\s+income\s+(summary|detail)", re.I), "Cash & Fixed Income"),
    (re.compile(r"cash\s+[&]\s+fixed\s+income", re.I), "Cash & Fixed Income"),
    (re.compile(r"equity\s+summary", re.I), "Equity Summary"),
    (re.compile(r"equity\s+detail", re.I), "Equity Detail"),
]


def _preferred_sheet_name_from_title(text: str) -> str | None:
    """If text matches a known report type, return the target sheet name; else None."""
    if not (text and isinstance(text, str)):
        return None
    s = text.strip()
    for pattern, sheet_name in REPORT_TITLE_TO_SHEET:
        if pattern.search(s):
            return sheet_name
    return None


def _cell_value(c) -> str | int | float:
    """
    Prefer numeric type for Excel (so calculations work); otherwise return cleaned string.
    Strips $ € £ and commas; handles trailing %; parenthetical negatives (123.45); rounds to 2 decimals.
    """
    if c is None:
        return ""
    if isinstance(c, (int, float)) and not isinstance(c, bool):
        return round(c, 2) if isinstance(c, float) and c != int(c) else c
    s = str(c).strip()
    if not s:
        return ""
    # Parenthetical negative: (308.60) or ($37,303.03)
    if s.startswith("(") and s.endswith(")"):
        inner = s[1:-1].strip().lstrip("$€£\u00a0").replace(",", "")
        try:
            val = float(inner)
            return round(-val, 2) if abs(val) >= 0.01 or val == 0 else -val
        except ValueError:
            pass
    # "09 $24,157,595.24" or "24 $24,284,278.98" -> take the dollar amount part only
    m = re.match(r"^\d+\s+[\$€£]?\s*([\d,]+\.?\d*)\s*$", s)
    if m:
        try:
            val = float(m.group(1).replace(",", ""))
            return round(val, 2) if abs(val) >= 0.01 or val == 0 else val
        except ValueError:
            pass
    # Strip currency symbols and commas for parsing
    is_pct = s.endswith("%")
    if is_pct:
        s = s[:-1].strip()
    clean = s.lstrip("$€£\u00a0").replace(",", "")
    try:
        if "." in clean or "e" in clean.lower():
            val = float(clean)
            if is_pct:
                val = val / 100.0
            if abs(val) >= 0.01 or val == 0:
                val = round(val, 2)
            return val
        if clean.isdigit() or (clean.startswith("-") and clean[1:].isdigit()):
            return int(clean)
    except ValueError:
        pass
    return s


def _merge_fragmented_row(cells: list) -> list:
    """
    Merge cells that are fragments of one value so numbers and headers stay in one cell.
    - "15,088,442.", "61" -> "15,088,442.61"
    - "22,913,59", "5.63" -> "22,913,595.63"
    - "Beginni", "n", "g" -> "Beginning"
    - "1,421,910.", "03 1,494,773.17" -> "1,421,910.03", "1,494,773.17"
    """
    if not cells:
        return []
    out = []
    for c in cells:
        s = (str(c) if c is not None else "").strip()
        if s and isinstance(c, (int, float)) and not isinstance(c, bool):
            s = str(c)
        if not s:
            out.append("")
            continue
        if out and out[-1] != "":
            last = str(out[-1])
            # Merge single digit (e.g. "2" after "15,041,566.")
            if re.match(r"^\d$", s):
                out[-1] = last + s
                continue
            # Merge decimal part: last ends with "." and current is digits (e.g. "61" after "15,088,442.")
            if last.endswith(".") and re.match(r"^\d+$", s):
                out[-1] = last + s
                continue
            # Last ends with "." and current is "DD next_number" (e.g. "03 1,494,773.17"): merge DD, then append next_number
            if last.endswith(".") and re.match(r"^\d+\s+[\d,]+", s):
                m = re.match(r"^(\d+)\s+(.+)$", s)
                if m:
                    dec_part, rest = m.group(1), m.group(2).strip()
                    out[-1] = last + dec_part
                    # Push rest as new value (may be number like "1,494,773.17")
                    try:
                        rest_clean = rest.replace(",", "").lstrip("$€£")
                        if "." in rest_clean or re.search(r"\d", rest_clean):
                            out.append(float(rest_clean) if "." in rest_clean else int(rest_clean))
                        else:
                            out.append(rest)
                    except ValueError:
                        out.append(rest)
                    continue
            # Merge decimal part in next cell: last ends with digits and current is short .dd or d.dd (not a full amount)
            # e.g. "22,913,59" + "5.63" -> 22913595.63; avoid "24044839" + "924157595.24" -> one huge number
            if re.search(r"[\d,]+$", last) and re.match(r"^\d*\.?\d+$", s) and len(s) <= 8:
                try:
                    clean_last = last.replace(",", "").lstrip("$€£")
                    combined = clean_last + s
                    if "." in combined:
                        out[-1] = float(combined)
                    else:
                        out[-1] = int(combined)
                except ValueError:
                    out.append(s)
                continue
            # Merge word fragments: last ends with letter (4+ chars), current is 1–2 letters only (e.g. "Beginni" + "n" + "g")
            # Use 1–2 so we get "Beginning" from "Beginni"+"n"+"g" but not "Beginning"+"Endi" -> "BeginningEnding"
            if len(last) >= 4 and last[-1].isalpha() and re.match(r"^[a-zA-Z]{1,2}$", s):
                out[-1] = last + s
                continue
        out.append(s)
    return out


def _drop_empty_rows(rows: list[list]) -> list[list]:
    """Remove rows that are entirely empty or only whitespace."""
    return [
        row for row in rows
        if any(c is not None and str(c).strip() != "" for c in (row if isinstance(row, (list, tuple)) else [row]))
    ]


def _clean_table_rows(rows: list) -> list[list]:
    """Apply merge of fragmented cells and drop empty rows. Use for all table row sources."""
    merged = [_merge_fragmented_row(list(r) if isinstance(r, (list, tuple)) else [r]) for r in rows]
    return _drop_empty_rows(merged)


def _split_table_by_section_titles(rows: list[list]) -> list[tuple[str, list[list]]]:
    """
    If the table has rows that look like section titles (e.g. Asset Allocation, Portfolio Activity, Tax Summary),
    split into sub-tables so each gets its own section in Excel. Returns [(title, rows), ...].
    """
    if not rows:
        return []
    result = []
    current_title = None
    current_rows = []
    leading_rows = []
    for row in rows:
        cells = list(row) if isinstance(row, (list, tuple)) else [row]
        first = (cells[0] if cells else None) and str(cells[0]).strip()
        if first and SECTION_TITLE_PATTERNS.match(first):
            if current_title is not None and current_rows:
                result.append((current_title, current_rows))
            elif current_title is None and leading_rows:
                result.append(("Section", leading_rows))
                leading_rows = []
            current_title = first
            current_rows = []
            continue
        if current_title is not None:
            current_rows.append(row)
        else:
            leading_rows.append(row)
    if current_title is not None and current_rows:
        result.append((current_title, current_rows))
    elif leading_rows:
        result.append(("Section", leading_rows))
    return result if result else [("Section", rows)]


def _page_sections_with_headings(page, page_num: int):
    """
    Yield (section_name, heading_rows, data_rows) for the page.
    Uses positioned text and tables so we get: heading, then table, then next heading, then table.
    """
    # Get text lines with position (top, bottom)
    if not hasattr(page, "extract_text_lines"):
        return
    text_lines = page.extract_text_lines() or []
    find_tables_kw = {"table_settings": TABLE_SETTINGS} if hasattr(page, "find_tables") else {}
    tables = page.find_tables(**find_tables_kw) if hasattr(page, "find_tables") else []

    # Build list of (top, kind, payload): "text" -> line dict, "table" -> (bbox, rows)
    elements = []
    for line in text_lines:
        text = (line.get("text") or "").strip()
        if not text:
            continue
        top = float(line.get("top", 0))
        bottom = float(line.get("bottom", top))
        elements.append((top, "text", {"text": text, "top": top, "bottom": bottom}))
    for tbl in tables:
        bbox = tbl.bbox if hasattr(tbl, "bbox") else (0, 0, 0, 0)
        try:
            rows = tbl.extract() or []
        except Exception:
            rows = []
        if not rows:
            continue
        rows = _clean_table_rows(rows)
        if not rows:
            continue
        top = float(bbox[1])
        elements.append((top, "table", {"bbox": bbox, "rows": rows}))

    if not elements:
        return
    elements.sort(key=lambda x: (x[0], 0 if x[1] == "text" else 1))

    prev_table_bottom = None
    section_idx = 0
    for _, kind, payload in elements:
        if kind == "text":
            continue  # we'll attach text to the next table or flush as section
        if kind == "table":
            table_top = payload["bbox"][1]
            table_bottom = payload["bbox"][3]
            # Heading = text lines that end just above this table
            heading_rows = []
            for line in text_lines:
                t = (line.get("text") or "").strip()
                if not t:
                    continue
                bottom = float(line.get("bottom", 0))
                top_ln = float(line.get("top", 0))
                if prev_table_bottom is not None and top_ln < prev_table_bottom + 5:
                    continue
                if bottom <= table_top + HEADING_GAP_PT and top_ln >= (prev_table_bottom or 0) - 5:
                    heading_rows.append(t)
            rows = payload["rows"]
            sub_tables = _split_table_by_section_titles(rows)
            for sub_title, sub_rows in sub_tables:
                if not sub_rows:
                    continue
                section_idx += 1
                # Use sub-table title (e.g. Asset Allocation) as section name; keep page heading as first line if present
                head = [sub_title] if sub_title != "Section" else (heading_rows or [f"Page{page_num}_T{section_idx}"])
                if heading_rows and sub_title != "Section":
                    head = heading_rows[:1] + [sub_title]  # period/context then table title
                name = (sub_title[:28] + f"_{section_idx}") if sub_title != "Section" else ((heading_rows[0][:28] + f"_{section_idx}") if heading_rows else f"Page{page_num}_T{section_idx}")
                yield (_safe_sheet_name(name, section_idx), head, sub_rows)
            prev_table_bottom = table_bottom

    # If no grid tables, group text lines by vertical gap: first line of group = heading, rest = table
    if not tables and text_lines:
        text_lines_sorted = sorted(
            [{"text": (l.get("text") or "").strip(), "top": float(l.get("top", 0)), "bottom": float(l.get("bottom", 0))}
             for l in text_lines if (l.get("text") or "").strip()],
            key=lambda x: x["top"],
        )
        if not text_lines_sorted:
            return
        group = [text_lines_sorted[0]["text"]]
        group_start = text_lines_sorted[0]["top"]
        for i in range(1, len(text_lines_sorted)):
            line = text_lines_sorted[i]
            gap = line["top"] - (text_lines_sorted[i - 1]["bottom"])
            if gap > SECTION_GAP_PT and group:
                # Flush group: first line = heading, rest = rows (split on 2+ spaces); then merge fragments
                heading = group[0]
                section_idx += 1
                rows = []
                for g in group[1:]:
                    parts = re.split(r"[\t ]{2,}", g)
                    rows.append(parts if len(parts) > 1 else [g])
                rows = _clean_table_rows(rows)
                yield (_safe_sheet_name(heading[:28] + f"_{section_idx}", section_idx), [heading], rows)
                group = []
            group.append(line["text"])
        if group:
            heading = group[0]
            section_idx += 1
            rows = []
            for g in group[1:]:
                parts = re.split(r"[\t ]{2,}", g)
                rows.append(parts if len(parts) > 1 else [g])
            rows = _clean_table_rows(rows)
            yield (_safe_sheet_name(heading[:28] + f"_{section_idx}", section_idx), [heading], rows)


def _normalize_row(row) -> list:
    """Turn a table row into a list of cell values (numbers preserved where possible)."""
    if isinstance(row, (list, tuple)):
        return [_cell_value(c) for c in row]
    return [_cell_value(row)]


def _parse_summary_lines(heading_rows: list[str]) -> tuple[str, list[list], list[str]]:
    """
    From heading lines above a table, get section title, optional key-value summary, and any
    lines that look like table headers (to be prepended to the data table).
    Returns (title, summary_rows, table_header_lines). summary_rows is list of [label, value].
    table_header_lines are raw lines to use as the first row(s) of the data table.
    """
    if not heading_rows:
        return "Section", [], []
    title = heading_rows[0].strip()
    if len(heading_rows) == 1:
        return title, [], []

    summary_rows = []
    table_header_lines = []
    for line in heading_rows[1:]:
        line = (line or "").strip()
        if not line:
            continue
        # Key-value summary: "Label: value" or "Label - value"
        if ":" in line:
            idx = line.index(":")
            summary_rows.append([line[:idx].strip(), line[idx + 1 :].strip()])
        elif " - " in line and not re.search(r"\d{2,}", line):
            a, _, b = line.partition(" - ")
            summary_rows.append([a.strip(), b.strip()])
        else:
            # Could be a table header row (multiple columns when split on 2+ spaces) or body text
            parts = re.split(r"  +", line)
            if len(parts) >= 2 and len(line) < 120:
                table_header_lines.append(line)
            else:
                # Single block of text or long line: treat as summary row (label, value) or skip
                if len(parts) == 2:
                    summary_rows.append([parts[0].strip(), parts[1].strip()])
                elif not table_header_lines:
                    summary_rows.append([line, ""])
                else:
                    table_header_lines.append(line)
    return title, summary_rows, table_header_lines


def _split_table_cell(cell: str) -> list:
    """
    Try to split a single cell that may contain tabular data into columns.
    Uses 2+ spaces as column separator; if none, tries splitting before numbers (e.g. "Name 1,234.56 2,345.67").
    """
    if not (cell and isinstance(cell, str)):
        return [cell] if cell is not None else [""]
    cell = cell.strip()
    if not cell:
        return [""]
    parts = re.split(r"  +", cell)
    if len(parts) > 1:
        return [_cell_value(p) for p in parts]
    # Two or more spaces before a digit (amounts)
    parts = re.split(r"  +(?=[\d$€£])", cell)
    if len(parts) > 1:
        return [_cell_value(p) for p in parts]
    # Single space before an amount (digits, optional commas, decimal): "Name 15,088.61 16,000.00" -> [Name, 15,088.61, 16,000.00]
    parts = re.split(r" ([\d][\d,]*\.[\d]+)", cell)
    if len(parts) > 1:
        out = []
        for i, p in enumerate(parts):
            p = p.strip()
            if not p:
                continue
            if i % 2 == 1:
                out.append(_cell_value(p))
            else:
                out.append(_cell_value(p))
        if len(out) > 1:
            return out
    return [_cell_value(cell)]


def _normalize_table_rows(data_rows: list) -> list[list]:
    """
    Ensure all rows have the same length (pad with empty strings).
    If every row is single-cell, try splitting into columns (2+ spaces, or space-before-number).
    """
    if not data_rows:
        return []
    rows_as_lists = []
    for row in data_rows:
        if isinstance(row, (list, tuple)):
            r = [str(c).strip() if c is not None else "" for c in row]
        else:
            r = [str(row).strip()]
        rows_as_lists.append(r)

    # If all rows are single-cell, try splitting into columns
    if all(len(r) == 1 for r in rows_as_lists):
        split_rows = []
        for r in rows_as_lists:
            split_rows.append(_split_table_cell(r[0]))
        if split_rows and max(len(s) for s in split_rows) > 1:
            rows_as_lists = split_rows

    max_cols = max(len(r) for r in rows_as_lists)
    out = []
    for r in rows_as_lists:
        vals = [_cell_value(c) if isinstance(c, str) else c for c in r]
        out.append(vals + [""] * (max_cols - len(r)))
    return out


def _write_section_to_sheet(ws, sec_name: str, heading_rows: list, data_rows: list, start_row: int = 1) -> int:
    """
    Write one section to a worksheet like the PDF: section title, optional summary table,
    then the main data table with header row and columns. Uses bold for title and table header.
    Returns the next row number after this section (so callers can append more sections).
    """
    title, summary_rows, table_header_lines = _parse_summary_lines(heading_rows)
    row_num = start_row

    # Section title (bold)
    ws.cell(row=row_num, column=1, value=title).font = Font(bold=True)
    row_num += 1

    # Optional summary as 2-column table (label | value)
    if summary_rows:
        for label, value in summary_rows:
            ws.cell(row=row_num, column=1, value=label)
            ws.cell(row=row_num, column=2, value=value)
            row_num += 1
        row_num += 1  # blank row after summary

    # Prepend any header lines (that were above the table in the PDF) to the data table
    combined_data = []
    for line in table_header_lines:
        parts = re.split(r"  +", line)
        combined_data.append(parts if len(parts) > 1 else [line])
    combined_data.extend(data_rows)
    data_rows = combined_data

    # Main data table: header row + data rows
    table_rows = _normalize_table_rows(data_rows)
    if not table_rows:
        if row_num == start_row + 1 and not summary_rows:
            ws.cell(row=row_num, column=1, value="(No table data)")
            row_num += 1
        return row_num

    # Table header (first row, bold)
    for col_idx, val in enumerate(table_rows[0], start=1):
        cell = ws.cell(row=row_num, column=col_idx, value=_cell_value(val))
        cell.font = Font(bold=True)
    row_num += 1

    # Data rows
    for r in table_rows[1:]:
        for col_idx, val in enumerate(r, start=1):
            ws.cell(row=row_num, column=col_idx, value=_cell_value(val) if not isinstance(val, (int, float)) else val)
        row_num += 1

    # Auto-fit column widths for this section's columns (only if we're the first section or single-sheet)
    num_cols = len(table_rows[0]) if table_rows else 2
    for col_idx in range(1, num_cols + 1):
        col_letter = get_column_letter(col_idx)
        max_len = 0
        for r in range(start_row, row_num):
            cell = ws.cell(row=r, column=col_idx)
            if cell.value is not None:
                max_len = max(max_len, min(50, len(str(cell.value))))
        if max_len > 0:
            current_width = ws.column_dimensions[col_letter].width or 0
            ws.column_dimensions[col_letter].width = max(current_width, max_len + 1)
    return row_num


def extract_sections_from_pdf(pdf_path: str) -> list[tuple[str, list, list]]:
    """
    Extract all tables/sections from the PDF in document order.
    Returns list of (section_name, heading_rows, data_rows).
    Same structure used for Excel and JSON; no file is written.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("File must be a .pdf")

    sections = []
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, start=1):
            if total_pages > 1:
                log.info("Page %d/%d", page_num, total_pages)
            used_sections = False
            if hasattr(page, "extract_text_lines"):
                for sec_name, heading_rows, data_rows in _page_sections_with_headings(page, page_num):
                    sections.append((sec_name, heading_rows, [_normalize_row(r) for r in data_rows]))
                    used_sections = True
            if not used_sections:
                tables = page.extract_tables()
                if tables:
                    for i, table in enumerate(tables):
                        if not table:
                            continue
                        name = f"Page{page_num}" if len(tables) == 1 else f"Page{page_num}_T{i+1}"
                        heading_rows = [name]
                        cleaned = _clean_table_rows(table)
                        data_rows = [_normalize_row(r) for r in cleaned]
                        sections.append((name, heading_rows, data_rows))
                else:
                    text = page.extract_text()
                    if text and text.strip():
                        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
                        if lines:
                            heading = lines[0]
                            rows = []
                            for line in lines[1:]:
                                parts = re.split(r"[\t ]{2,}", line)
                                rows.append(parts if len(parts) > 1 else [line])
                            rows = _clean_table_rows(rows)
                            data_rows = [_normalize_row(r) for r in rows]
                            sections.append((f"Page{page_num}", [heading], data_rows))
                    else:
                        sections.append((f"Page{page_num}", ["(No text extracted from this page)"], []))

    def _section_has_data(data_rows):
        if not data_rows:
            return False
        for r in data_rows:
            if isinstance(r, (list, tuple)):
                if r and any(c is not None and str(c).strip() != "" for c in r):
                    return True
            elif r is not None and str(r).strip() != "":
                return True
        return False

    merged = []
    pending_title = None
    for sec_name, heading_rows, data_rows in sections:
        if not _section_has_data(data_rows):
            if heading_rows and heading_rows[0].strip():
                pending_title = heading_rows[0].strip() if not pending_title else f"{pending_title} — {heading_rows[0].strip()}"
            continue
        if pending_title:
            heading_rows = [pending_title, *heading_rows]
            pending_title = None
        merged.append((sec_name, heading_rows, data_rows))
    return merged


def _cell_to_json(c):
    """One cell to a JSON-safe value."""
    if c is None:
        return None
    if isinstance(c, (int, float)) and not isinstance(c, bool):
        return c
    s = str(c).strip()
    return s if s else None


def _build_header_grid(rows: list[list]) -> dict | None:
    """
    Build row/column header view from a table: first row = column_headers, first column = row_headers.
    Returns { "column_headers": [...], "row_headers": [...], "data": [[...], ...] } so that
    value at (row_headers[i], column_headers[j]) = data[i][j]. Enables (x, y) lookup by heading names.
    """
    if not rows or len(rows) < 2:
        return None
    first_row = rows[0]
    col_headers = [_cell_to_json(c) for c in (first_row if isinstance(first_row, (list, tuple)) else [first_row])]
    if not col_headers or all(c is None or (isinstance(c, str) and not c.strip()) for c in col_headers):
        return None
    row_headers = []
    data = []
    for r in rows[1:]:
        row = r if isinstance(r, (list, tuple)) else [r]
        row_headers.append(_cell_to_json(row[0]) if row else None)
        data.append([_cell_to_json(row[j]) if j < len(row) else None for j in range(1, len(col_headers) + 1)])
    return {"column_headers": col_headers, "row_headers": row_headers, "data": data}


def _sections_to_json_serializable(sections: list[tuple]) -> list[dict]:
    """Turn (name, heading_rows, data_rows) into list of dicts safe for JSON (no tuples, consistent types)."""
    out = []
    for sec_name, heading_rows, data_rows in sections:
        # Headings: list of strings (first line can be section title)
        headings = []
        for h in (heading_rows or []):
            if isinstance(h, (list, tuple)):
                headings.append(" ".join(str(x) for x in h if x is not None))
            else:
                headings.append(str(h) if h is not None else "")
        # Rows: list of lists; cells as numbers or strings
        rows = []
        for r in (data_rows or []):
            row = r if isinstance(r, (list, tuple)) else [r]
            cells = [_cell_to_json(c) for c in row]
            rows.append(cells)
        section_dict = {"name": str(sec_name), "headings": headings, "rows": rows}
        # Grid size for verification: how many rows/columns were extracted
        section_dict["row_count"] = len(rows)
        section_dict["column_count"] = len(rows[0]) if rows else 0
        # Add header-grid view for (row_heading, column_heading) → value lookup
        # Canonical key is (row_index, column_index); headers are labels and may repeat
        grid = _build_header_grid(rows)
        if grid:
            section_dict["column_headers"] = grid["column_headers"]
            section_dict["row_headers"] = grid["row_headers"]
            section_dict["data"] = grid["data"]
        out.append(section_dict)
    return out


def _write_json_from_sections(sections: list[tuple], out: Path, overwrite: bool = True) -> None:
    """Write sections to a JSON file (used for one-stream Excel + JSON output)."""
    if out.exists() and not overwrite:
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"sections": _sections_to_json_serializable(sections)}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    log.info("Wrote %d section(s) to %s", len(sections), out)


def pdf_to_json(
    pdf_path: str,
    output_path: str | None = None,
    overwrite: bool = True,
) -> str:
    """
    Extract all tables/sections from the PDF and write them to a JSON file.
    Structure: { "sections": [ { "name": "...", "headings": [...], "rows": [[...], ...] }, ... ] }
    Same data as Excel, so you can edit/filter the JSON then convert to Excel or QB format later.
    """
    pdf_path = Path(pdf_path)
    out = Path(output_path or pdf_path.with_suffix(".json"))
    if out.exists() and not overwrite:
        raise FileExistsError(f"Output exists (use --overwrite to replace): {out}")

    sections = extract_sections_from_pdf(pdf_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    _write_json_from_sections(sections, out, overwrite)
    return str(out)


def pdf_tables_to_excel(
    pdf_path: str,
    output_path: str | None = None,
    overwrite: bool = True,
    single_sheet: bool = False,
    write_json: bool = False,
    json_path: str | Path | None = None,
) -> str:
    """
    Extract every table from the PDF and write to one Excel file.

    By default (single_sheet=False), creates one sheet per section so each sheet mirrors
    the PDF: a section title, optional summary (key-value lines as a 2-column table),
    then the main data table with header row and columns. Organized and readable.

    If single_sheet=True, writes one sheet "Extracted" with all sections in that same
    format (title, summary, table, blank rows, next section...).

    If write_json=True and json_path is set, writes the same extraction to a JSON file
    (one stream: one extraction → Excel + JSON).
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("File must be a .pdf")

    out = Path(output_path or pdf_path.with_suffix(".xlsx"))
    if out.exists() and not overwrite:
        raise FileExistsError(f"Output exists (use --overwrite to replace): {out}")

    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        sections = extract_sections_from_pdf(pdf_path)
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg or "encrypted" in msg:
            raise ValueError("PDF appears password-protected or encrypted; not supported.") from e
        if "invalid" in msg or "cannot read" in msg or "failed" in msg:
            raise ValueError("PDF could not be read (corrupt or invalid file).") from e
        raise

    wb = Workbook()
    wb.remove(wb.active)

    if not sections:
        ws = wb.create_sheet(title="Info")
        ws.append(["No tables or structured data could be extracted from this PDF."])
        wb.save(out)
        if write_json and json_path:
            _write_json_from_sections([], Path(json_path), overwrite)
        log.info("Wrote 1 sheet to %s", out)
        return str(out)

    if single_sheet:
        ws = wb.create_sheet(title="Extracted")
        next_row = 1
        for sec_name, heading_rows, data_rows in sections:
            next_row = _write_section_to_sheet(ws, sec_name, heading_rows, data_rows, start_row=next_row)
            next_row += 2  # blank rows between sections
        sheet_count = 1
    else:
        # Prefer target-format sheet names (see EXPECTED_FORMAT.md) when section matches
        used_sheet_names = {}
        for idx, (sec_name, heading_rows, data_rows) in enumerate(sections):
            preferred = _preferred_sheet_name_from_title(sec_name)
            if not preferred and heading_rows:
                preferred = _preferred_sheet_name_from_title(heading_rows[0])
            if preferred:
                base = _safe_sheet_name(preferred, idx + 1)
                count = used_sheet_names.get(base, 0) + 1
                used_sheet_names[base] = count
                name = _safe_sheet_name(f"{base.strip()} {count}" if count > 1 else base, idx + 1)
            else:
                name = _safe_sheet_name(sec_name, idx + 1)
            ws = wb.create_sheet(title=name)
            _write_section_to_sheet(ws, sec_name, heading_rows, data_rows)
        sheet_count = len(sections)

    wb.save(out)
    if write_json and json_path:
        _write_json_from_sections(sections, Path(json_path), overwrite)
    log.info("Wrote %d sheet(s) to %s", sheet_count, out)
    return str(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract all tables from a PDF into an Excel file (no API key required)."
    )
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("-o", "--output", default=None, help="Output .xlsx path")
    parser.add_argument("--no-overwrite", action="store_false", dest="overwrite", default=True, help="Do not overwrite; fail if output file already exists")
    parser.add_argument("--separate-sheets", action="store_true", dest="separate_sheets", help="One sheet per section (default: one sheet with all sections in order)")
    args = parser.parse_args()

    try:
        log.info("Input: %s", args.pdf)
        result = pdf_tables_to_excel(args.pdf, args.output, overwrite=args.overwrite, single_sheet=not args.separate_sheets)
        print(f"Saved: {result}")
        return 0
    except (FileNotFoundError, ValueError, FileExistsError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
