# Hybrid extraction: how it works

The **hybrid** pipeline combines fast library-based extraction (pdfplumber/PyMuPDF) with the vision-language (VL) model only where needed. That keeps most pages fast and uses VL only on pages the library handles poorly (e.g. complex layout, images, or scanned content).

## Flow (high level)

1. **Library extraction**  
   All pages are extracted with the usual library stack (`extract_sections_from_pdf` → pdfplumber/PyMuPDF). Each page gets one or more sections (tables, key-value blocks, etc.).

2. **Bad-page detection**  
   For each page we check whether any section “looks like” a real table (multi-column, structured data). Pages where **no** section passes this check are marked as **bad** and sent to VL.

3. **VL only on bad pages**  
   The vision model runs only on the bad page numbers (`page_ranges=bad_pages`). So you get VL quality only where the library failed, and avoid running VL on every page.

4. **Merge**  
   Final output = library sections for “good” pages + VL sections for bad pages, in document order.

5. **Output**  
   Canonical JSON is written (same format as `run.py json` / VL JSON), so you can run `run.py from-json` to get Excel. Meta includes hybrid flags and **per-page VL timing**.

## Where timing is stored

When VL is used, the written JSON `meta` includes:

- **`vl_timing_seconds`** – total VL inference time (seconds).
- **`vl_per_page_seconds`** – list of seconds per VL page (same order as `vl_page_numbers`).
- **`vl_page_numbers`** – list of 1-based page numbers that were sent to VL.
- **`vl_page_timings`** – per-page timing: `[{"page": N, "seconds": S}, ...]` for each VL page.

So you can see exactly how long each VL page took. If no bad pages are found, VL is not run and these fields are omitted.

## Commands

```bash
# Hybrid → JSON (with per-page timing in meta when VL is used)
python run.py hybrid report.pdf --schema-type broker_statement -o output/report_hybrid.json

# Optional: also produce Excel
python run.py hybrid report.pdf --schema-type broker_statement -o output/report_hybrid.json --excel

# Or convert JSON to Excel later
python run.py from-json output/report_hybrid.json -o output/report_hybrid.xlsx
```

## Code locations

- **Entrypoint:** `run.py hybrid` → `cmd_hybrid` → `hybrid_extract.hybrid_pdf_to_json`.
- **Hybrid logic:** `hybrid_extract.py` (bad-page detection, VL call, merge, JSON write).
- **Library extraction:** `tables_to_excel.extract_sections_from_pdf`, `filter_sections_to_tables_only`, `_looks_like_table`.
- **VL extraction:** `extract_vl.extract_pdf_with_vl` (returns `text` and `meta` with `per_page_seconds`, `page_numbers`, `total_seconds`).

## Bad-page rule

A page is **bad** if, after library extraction, it has **no** section that passes `_looks_like_table` (in `tables_to_excel`). That typically means: no multi-column rows, too few cells, or only long prose/junk. Those pages are re-run through the VL model.
