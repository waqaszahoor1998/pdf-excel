# PDF → Excel / QB pipeline: roadmap

This document is the **plan for future updates** to the PDF→Excel (QB-style) pipeline. It lists what to do, in what order, and how to do it.

**Current state:** Local extraction (pdfplumber), QB-format merge (pdf_to_qb.py), color coding, fragmentation fixes for numbers/words. One flow: upload PDF → one Excel.

---

## Target: results like the manual QB Automation Sheet

**Goal:** When you upload a PDF (e.g. a combined statement), the program should produce an Excel workbook that is **acceptable in the same way your QB Automation Sheet is** — well structured, maintainable, with the right sheets, column names, colors, and formulas so it can be used (or lightly touched up) instead of building it by hand.

The manual QB sheet is the quality bar. The phases below are ordered so that, once done, the automated output gets as close as possible to that.

| What the manual QB sheet has | Which phase gets us there |
|------------------------------|----------------------------|
| Same sheet names and grouping (Net Assets, Operations, PLSummary, etc.) | Already in place (pdf_to_qb + section naming). |
| Color coding (green, yellow, orange, blue) | Already in place. |
| No fragmented numbers or split headers | **Phase 1** (extraction quality). |
| Same column names (Account Name, Market Value, BOM, EOM, Cash In, Cash Out, PNL) | **Phase 2** (column normalization + order). |
| Formulas where there are totals or checks (yellow cells) | **Phase 3** (formulas). |
| Same layout style (side‑by‑side blocks on one sheet, or stacked) | **Phase 2/5** (column order; optional template fill for exact layout). |
| Works for different custodians (JPM, Goldman, Wells Fargo) | **Phase 4** (more PDF types). |
| Exact copy of your QB layout (same cells, same positions) | **Phase 5** (template-based: fill your actual QB template from extracted data). |

**Will this achieve “similar results” to the sample?**  
- **Phases 1–3** are the core: they give you clean data, correct column names and order, and formulas. That gets you **most of the way** to the same level of quality and usability as the manual sheet for a **single PDF**.  
- **Phase 4** makes it work for **other custodians** so the same QB-style output is possible from different statement types.  
- **Phase 5 (template)** is how you get **as close as possible** to the exact look and structure of the manual sheet: the program fills your real QB template from the extracted data instead of building a new workbook from scratch.

**Important limitation:** The manual QB workbook may have been built from **multiple** statements (e.g. JPM + Goldman + Wells Fargo) and some manual curation. The pipeline today is **one PDF → one Excel**. To get one combined workbook from several PDFs, we’d add a “multi-PDF merge” step (e.g. run extraction on each PDF, then merge results into one QB-format workbook); that can be added after Phase 4 if you need it.

---

## Phase 1 — Extraction quality (do first)

**Goal:** Fewer split numbers and headers so the Excel output is closer to the source PDF.

### 1.1 Split “double number” cells

| What | Cells that contain two numbers in one string (e.g. `"03 1,494,773.17"`) should become two columns or one merged value. |
| How | In `tables_to_excel.py`: after `_merge_fragmented_row`, add a pass (or extend `_split_table_cell`) that detects a cell matching `\d+\s+[\d,]+\.\d+` and splits it into two values; then re-run row merge so the first part can merge with the previous cell if needed. Test on 9004 PDF Asset Allocation sheet. |
| Where | `tables_to_excel.py`: `_normalize_table_rows` or a new `_split_double_number_cells()`. |
| Done | [ ] |

### 1.2 More merge patterns (optional)

| What | Extend `_merge_fragmented_row` for any new split patterns you see (e.g. currency symbols, dates split across cells). |
| How | Add rules when you find a concrete example in a new PDF; document the pattern in a comment. |
| Where | `tables_to_excel.py`: `_merge_fragmented_row`. |
| Done | [ ] |

**Phase 1 sign-off:** Run pipeline on 9004 PDF; spot-check Asset Allocation and Portfolio Activity; fewer obviously split values.

---

## Phase 2 — Column and sheet structure

**Goal:** Output columns and sheet names align with QB so downstream tools (or formulas) can rely on them.

### 2.1 Column name normalization

| What | Map extracted column labels to standard names: e.g. “Beginning Market Value” → BOM, “Ending Market Value” → EOM, “Account Name”, “Market Value”, “Cash In”, “Cash Out”, “PNL”. |
| How | In `pdf_to_qb.py` (or a small helper module): when writing a row, if the row looks like a header row, run each cell through a mapping dict (e.g. `COLUMN_ALIASES`) and replace with the canonical name. Optionally do the same in `tables_to_excel.py` when writing the first data row of a section. |
| Where | New: `pdf_to_qb.py` or `column_mapping.py` with `normalize_header_row(row)`; call before writing header rows. |
| Done | [ ] |

### 2.2 Optional: reorder columns to QB order

| What | For known sheet types (e.g. PLSummary), ensure column order matches QB: Account Name, Market Value, Cash In, Cash Out, PNL, Market Value (EOM). |
| How | After normalization, if sheet type is known, reorder columns by a fixed list (missing columns = blank). Only do for sheets we explicitly support. |
| Where | Same module as 2.1; apply after `normalize_header_row` when target order is defined. |
| Done | [ ] |

**Phase 2 sign-off:** QB-format output has consistent header names (and optionally order) for at least Period Summary, Asset Allocation, Portfolio Activity, Tax Summary.

---

## Phase 3 — Formulas and checks

**Goal:** Where the sample has formulas (yellow cells), the output can have real formulas so the workbook is calculation-ready.

### 3.1 Detect “totals” and “check” rows

| What | Identify rows that should have a formula: e.g. “Totals” row = sum of numeric column above; “Chk” or “Check” column = difference of two values. |
| How | In transform: when writing a block, track the data range (e.g. rows 5–17); when we write a row whose first cell is “Totals”, insert a formula in numeric columns (e.g. `=SUM(B5:B17)`) instead of copying a raw value if the cell is empty or looks like a total. Use openpyxl to set `cell.value = "=SUM(...)"`. |
| Where | `pdf_to_qb.py`: in the block-writing loop, keep `data_start_row`, `data_end_row`, and column indices; when row is totals, write formulas for numeric columns. |
| Done | [ ] |

### 3.2 Yellow fill for formula cells

| What | Any cell we write with a formula string (starting with `=`) gets yellow fill. |
| How | Already implemented: `_is_formula_or_check(val)` and `FILL_FORMULA`. Ensure we don’t overwrite fill when writing formula cells. |
| Where | `pdf_to_qb.py` (already in place; verify when adding 3.1). |
| Done | [ ] |

**Phase 3 sign-off:** For at least one sheet type (e.g. Portfolio Activity), Totals row has real `=SUM(...)` formulas and yellow fill.

---

## Phase 4 — More PDF types and robustness

**Goal:** Other custodians (e.g. Goldman, Wells Fargo) and statement layouts produce the right sheet names and grouping.

### 4.1 Add section patterns for other brokers

| What | When you have a sample PDF from another custodian, add section-title patterns so we recognize their “Account Summary”, “Portfolio Activity”, etc., and map to the same QB sheet names. |
| How | Add regex entries to `REPORT_TITLE_TO_SHEET` in `tables_to_excel.py` and/or to `_target_sheet_name` in `pdf_to_qb.py`; document in `docs/EXPECTED_FORMAT.md`. |
| Where | `tables_to_excel.py`, `pdf_to_qb.py`, `docs/EXPECTED_FORMAT.md`. |
| Done | [ ] |

### 4.2 Per-custodian tweaks (optional)

| What | If a custodian’s PDF has a different layout (e.g. different header row position), add a small custodian-specific branch (e.g. “if JPM then …”, “if Goldman then …”) only where necessary. |
| How | Prefer one set of rules; add custodian-specific logic only when the same rule set can’t handle both. |
| Where | `tables_to_excel.py` or `pdf_to_qb.py` with clear comments. |
| Done | [ ] |

**Phase 4 sign-off:** At least one non-JPM statement runs through the pipeline and produces sensible QB-style sheets.

---

## Phase 5 — Template and tests (optional)

**Goal:** Option to fill a fixed QB template; regression safety.

### 5.1 Template-based output (optional)

| What | Option: user provides a QB template .xlsx (fixed sheets/columns); we fill it from extracted data instead of building the workbook from scratch. |
| How | New mode or script: load template, locate “input” ranges or sheet names, write extracted tables into those ranges. Requires defining the template layout (which sheet, which columns). |
| Where | New file e.g. `fill_qb_template.py` or a branch in `pdf_to_qb.py` (e.g. `transform_extracted_to_qb(..., template_path=...)`). |
| Done | [ ] |

### 5.2 Automated tests for extraction + transform

| What | Tests that run extraction + QB transform on a checked-in sample PDF (or a tiny fixture) and assert: sheet names, row counts, presence of key headers, maybe color on Totals row. |
| How | pytest: fixture = path to 9004 PDF (or a 1–2 page stub); run `pdf_to_qb_excel`; load output and check `wb.sheetnames`, `ws.max_row` for “Asset Allocation”, “Tax Summary”, etc. |
| Where | `tests/test_pdf_to_qb.py` or extend `tests/test_extract.py`. |
| Done | [ ] |

**Phase 5 sign-off:** (Optional) Template path works for one template; tests run in CI and pass.

---

## Phase 6 — Scanned PDFs and password (later)

**Goal:** Support image-only PDFs and, if needed, password-protected PDFs.

### 6.1 OCR for scanned PDFs

| What | If the PDF has no extractable text (image-only), run OCR (e.g. Tesseract via pytesseract, or pdf2image + OCR) and then run table extraction on the OCR text/layout. |
| How | Detect “no text” (e.g. pdfplumber returns empty or very little text); call OCR pipeline; merge OCR output into a format pdfplumber or a second pass can use. Research: pdf2image, pytesseract, or cloud OCR if policy allows. |
| Where | New module e.g. `ocr_fallback.py`; called from `tables_to_excel.py` or app when extraction is empty. |
| Done | [ ] |

### 6.2 Password-protected PDFs

| What | Support opening PDFs that require a password (user provides password). |
| How | pdfplumber.open(path, password=...) if supported; add a password field in the app or CLI. Document security (password not stored). |
| Where | `tables_to_excel.py`, app (optional password input), README. |
| Done | [ ] |

**Phase 6 sign-off:** One scanned PDF runs through OCR path and produces Excel; password path works and is documented.

---

## Summary: will the phases get us to "perfect" (like the QB sample)?

- **Yes, for a single PDF.** Doing **Phases 1, 2, and 3** will get you output that is **close to the manual QB sheet** in structure, column names, colors, and formulas — good enough to use or lightly touch up instead of building the workbook by hand.
- **Phase 4** makes that true for **other custodians** (Goldman, Wells Fargo, etc.), not just the 9004-style JPM PDF.
- **Phase 5 (template)** is how you get **as close as possible** to the exact layout of your sample: the program fills your actual QB template so the result looks and behaves like the manually maintained sheet.
- **Multiple PDFs in one workbook:** If your manual QB book is built from several statements at once, we can add a "merge multiple PDFs into one QB workbook" step after Phase 4.

So: the phases and order are designed to get you to **acceptable, QB-style results** like the sample. Phases 1–3 are the main path; 4 and 5 extend it to more sources and to an exact template match.

---

## Order of work (recommended)

1. **Phase 1** — Improves quality immediately; no new concepts.
2. **Phase 2** — Makes the output “QB-ready” for column names (and order).
3. **Phase 3** — Adds formulas so the workbook is calculation-ready.
4. **Phase 4** — When you have another custodian’s PDF, add patterns and test.
5. **Phase 5** — When you want template fill or CI safety, add template mode and tests.
6. **Phase 6** — When you need scanned or password-protected PDFs, add OCR and password support.

---

## Quick reference: where things live

| Area | File(s) |
|------|--------|
| Extraction, merge rules, section naming | `tables_to_excel.py` |
| QB merge, colors, column normalization (future) | `pdf_to_qb.py` |
| App: upload → download | `app.py`, `templates/index.html` |
| Target format and color usage | `docs/EXPECTED_FORMAT.md` |
| This roadmap | `ROADMAP.md` |
| Original project plan | `docs/archive/PLAN.md` |

---

*Last updated: from “what we achieved / what’s next” summary.*
