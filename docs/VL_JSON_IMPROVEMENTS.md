# Improving VL extraction JSON: accuracy and precision

This doc covers how the VL (vision) pipeline produces JSON and how you can improve accuracy and precision.

---

## What the JSON contains

- **`sections`**: list of objects, each with:
  - **`name`**: section/table title (e.g. "Portfolio Activity", "REPORTABLE INCOME")
  - **`headings`**: column headers (one per column)
  - **`rows`**: data rows (list of lists; each inner list = one row of cells)
  - **`row_count`**, **`column_count`**: derived counts
  - **`page`**: (optional) 1-based page number in the PDF where this section was extracted

The vision model sees each page as an image and returns **plain text** (TAB-separated or pipe-separated). We parse that into the above structure. So accuracy depends on: (1) the **prompt**, (2) the **model**, and (3) **post-processing**.

---

## Timing (GPU)

When you run `extract_vl` with a CUDA build, the log shows:

- **Per page**: `VL page 1/5 (12.3 s)` — seconds to run the model on that page image.
- **Summary**: `VL timing: total 61.2 s, 12.2 s/page (GPU)` — total time and average per page.

Typical range with GPU (e.g. RTX 3060+): **~8–20 s per page** depending on resolution, table density, and GPU. CPU is much slower (minutes per page).

---

## Recent changes (Batch 3 — Mar 2026)

- **Broker and tax prompts** in `extract_vl.py` were tightened so the model is instructed to: use TAB between columns; output one table per section with a title line, header line, then data rows; include all total and subtotal rows; and for US Tax Summary, output Dividends and Distributions, Reportable Interest (including Bank Interest), Total Reportable Income, and Non-Reportable Items as separate tables with Current Month / Quarter to Date / Year to date.
- **Parser:** If the model uses spaces instead of TABs, the parser now splits on two or more spaces so table lines like `Portfolio Number    BASE CURRENCY    MANDATE NAME` become three columns instead of one. This improves JSON (and thus xlsx) when the model does not emit TABs.
- **Overview and US Tax Summary (Batch 4):** Broker prompt now explicitly requires extracting the Overview page (Portfolio Activity, Investment Results, Performance Summary, Performance (%)). Reportable Interest is defined as only: Corporate Interest, Non-US Interest, Bank Interest, Total Reportable Interest, Total Reportable Income—no dividend rows mixed in. Non-Reportable Items / Accrued Interest Paid at Purchase must be output as a separate table when present. US Tax Summary (Continued) must include all three columns (Current Month, Quarter to Date, Year to date) for Long Term Realized Gain, Total Realized Capital Gains, and Current Unrealized Gain (Loss). If the Overview is missing in a run (e.g. decode failures on early pages), re-running often yields a complete extraction.

---

## Ways to improve accuracy and precision

### 1. **Tune the prompt** (biggest lever)

The prompt is in `extract_vl.py`: `TABLE_EXTRACTION_PROMPT`. You can:

- **Narrow the task**: e.g. "Extract ONLY the following tables: Statement of Net Assets, Portfolio Activity. Ignore everything else."
- **Specify number format**: e.g. "Keep numbers as in the document: use commas for thousands (e.g. 1,234.56), no currency symbols in the value column."
- **Add your section names**: the prompt lists standard report titles; add yours so the model outputs consistent names (better for `title_to_sheet` and merging).
- **One table per page**: if each page has one main table, say "Output exactly one table: first line = title, second line = TAB-separated headers, then one row per line with TAB between cells."

Override from CLI:  
`.\venv\Scripts\python.exe -m extract_vl report.pdf --json out.json --prompt "Your custom prompt"`

### 2. **Higher image resolution**

In `extract_vl.py`, `pdf_pages_to_images()` uses `fitz.Matrix(2, 2)` (2x scale). For small text or dense tables, increase scale (e.g. 3x) so the model sees clearer text. Trade-off: larger images → more VRAM and slightly slower.

### 3. **Post-process the JSON**

- **Column count consistency**: some rows may have missing or extra cells; pad or trim to `column_count` (or to `len(headings)`).
- **Numeric normalization**: strip currency symbols, normalize commas/dots for decimals if you need to compute on values.
- **Merge duplicate sections**: if the same section name appears on multiple pages (e.g. "Portfolio Information"), you can merge them by name and keep `page` for reference.
- **Validation**: check `row_count`/`column_count` vs actual `rows`/`headings`; flag sections where they don’t match.

### 4. **Use `page` for auditing**

Each section can include **`page`** (1-based). Use it to:

- Trace back to the PDF page when something looks wrong.
- Filter or sort sections by page.
- Build reports like "sections by page" for QA.

### 5. **Two-pass or human-in-the-loop**

- **First pass**: run VL with `--max-pages N` to get a draft JSON.
- **Edit**: fix section names, align columns, remove junk rows in the JSON.
- **Second pass**: run `run.py from-json` to produce Excel. No need to re-run the model.

### 6. **Config and schema**

- **`config/qb_cleanup.json`**: `title_to_sheet` maps section names to sheet names; add entries for your PDFs so Excel sheet names are consistent.
- **`config/extract.json`**: if you add VL-related options (e.g. default `max_pages`, prompt path), you can tune without code changes.

---

## Summary

| Goal | Action |
|------|--------|
| **Faster feedback** | Check log: "VL timing: total X s, Y s/page (GPU)". |
| **More precise tables** | Refine `TABLE_EXTRACTION_PROMPT` (and optionally resolution). |
| **Trace to PDF** | Use **`page`** in each section. |
| **Cleaner data** | Post-process JSON (column alignment, number format, merge by name). |
| **Stable sheet names** | Add your section titles to `title_to_sheet` in `config/qb_cleanup.json`. |
