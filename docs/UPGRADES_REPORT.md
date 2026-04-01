# PDF–Excel / VL extraction — upgrades report

**Living document:** this report is updated as we implement changes. Use it to track what’s done and what’s next.

---

## Completed upgrades

### Batch 1 — Speed, page control, prompts, JSON quality (Mar 2025)

| # | Upgrade | What was done |
|---|--------|----------------|
| **1** | **GPU throughput & config** | Single Llama instance reused for all pages (no reload per page). New `config/vl.json`: `max_tokens`, `image_scale`, `temperature`, `max_vl_pages_per_run`. Env overrides: `VL_MAX_TOKENS`, `VL_IMAGE_SCALE`, `VL_MAX_PAGES_PER_RUN`. CLI: `--max-tokens`, `--image-scale`. Log line when GPU is used: "VL using GPU (n_gpu_layers=-1)". |
| **2** | **Page selection & throttling** | `--page-ranges` (e.g. `1-5,10-20`) to run VL only on specified pages. `max_vl_pages_per_run` in config caps total pages per run. `pdf_pages_to_images()` now takes `page_ranges` and `scale`; returns `(page_number, png_bytes)` so JSON page numbers match the PDF. |
| **3** | **Prompt profiles** | `--schema-type`: `generic`, `broker_statement`, `tax_statement`. New prompts: `BROKER_STATEMENT_PROMPT`, `TAX_STATEMENT_PROMPT`; `PROMPT_PROFILES` in `extract_vl.py`. |
| **4** | **Row/column normalization** | `_normalize_sections()` pads or trims each section’s rows to `column_count` so all rows are consistent before writing JSON. |
| **5** | **Run meta in JSON** | VL JSON output now includes a `meta` object: `pdf_name`, `pages_processed`, `vl_timing_seconds`, `vl_per_page_seconds`. |

**Files touched**

- `extract_vl.py`: config loading, page ranges, prompt profiles, normalization, meta, CLI args.
- `config/vl.json`: new file (max_tokens, image_scale, max_vl_pages_per_run, temperature, schema_type_default).

**Usage**

```bash
# With new options
python -m extract_vl "file.pdf" --json output/out.json --max-pages 5
python -m extract_vl "file.pdf" --json output/out.json --page-ranges 1-3,7-8 --schema-type broker_statement
python -m extract_vl "file.pdf" --json output/out.json --max-tokens 1024 --image-scale 2.0

# Then to Excel
python run.py from-json output/out.json -o output/out.xlsx
```

### Batch 2 — Comparison tool & Excel page column (Mar 2025)

| # | Upgrade | What was done |
|---|--------|----------------|
| **6** | **JSON comparison helper** | New `scripts/compare_vl_json.py`: compares two VL JSON files (section count, row/column counts per section, optional `--verbose` for sample cell-level diffs). Usage: `python scripts/compare_vl_json.py a.json b.json` or `--brief` / `-v`. |
| **7** | **Excel: page column** | When a section has a `page` field (from VL JSON), `_write_sections_to_workbook` now prepends a "Page" column to that section’s table (header + one page value per row). Applies in both single-sheet and multi-sheet modes. |

**Files touched**

- `scripts/compare_vl_json.py`: new script.
- `tables_to_excel.py`: in single-sheet and grouped branches, read `page` from section tuple; when present, prepend "Page" to headings and `[page]` to each data row before writing.

### Batch 3 — JSON/Excel quality: prompts & parser (Mar 2026)

| # | Upgrade | What was done |
|---|--------|----------------|
| **8** | **Broker & tax prompts** | `BROKER_STATEMENT_PROMPT` and `TAX_STATEMENT_PROMPT` expanded: (1) Use TAB between every column; (2) One table per section with title line, header line, then data rows (row label in first column, values in rest); (3) Include all total/subtotal rows; (4) Multi-block pages (e.g. Portfolio Info + “Duplicate copies sent to”) as separate tables; (5) Overview: Portfolio Activity (all rows), Investment Results, Performance; (6) US Tax Summary: Dividends and Distributions, Reportable Interest (incl. Bank Interest), Total Reportable Income, Non-Reportable Items, each with Current Month / Quarter to Date / Year to date. |
| **9** | **Parser: space-separated fallback** | When the model outputs spaces instead of TABs (e.g. “Portfolio Number    BASE CURRENCY    MANDATE NAME”), the parser now splits on 2+ spaces so we get proper columns. New `_split_line_to_cells(line, sep)` in `extract_vl.py`; all table parsing uses it so TAB and multi-space tables both produce correct JSON. |

**Files touched**

- `extract_vl.py`: prompt text for broker_statement and tax_statement; `_split_line_to_cells()`, `_parse_table_blocks()` updated to use it.

---

## Planned / next

*(Add items here as we plan or start new work.)*

- [ ] Conservative hybrid engine (text-first, VL fallback) — optional, carefully scoped.
- [ ] Web app: show VL run progress (e.g. "Page 3/10…") in the UI.
- [ ] Model exploration: pluggable alternative VL/document models.

---

## References

- **VL pipeline:** `docs/VL_PIPELINE_AND_LIBRARIES.md`
- **GPU setup:** `docs/VL_GPU_WHY_AND_FIX.md`
- **JSON improvements:** `docs/VL_JSON_IMPROVEMENTS.md`
- **Plan (phases):** `PLAN_VL.md`
