# Execution summary — Phases in progress

Quick reference for what was run and how to repeat or continue.

---

## What was executed

1. **Phase 1 (extraction)**  
   - Ran VL extraction on `sample_report.pdf` (3 pages; only 1 page had content).  
   - Output: `output/statement_12.json`, then `output/statement_12.xlsx` via `from-json`.  
   - Pipeline works: JSON has `page` in sections, so sheet grouping can use it.

2. **Phase 2 (QB sheet names by page)**  
   - Confirmed: `run.py from-json` uses `config/vl.json` → `page_to_sheet` when sections have `page`.  
   - Ran `from-json output/statement_11.json -o output/statement_11_qb.xlsx`.  
   - Result: Excel with sheets grouped by page (Contents, General Information, Overview, US Tax Summary as in config).  
   - No code change needed; config-driven and already in place.

---

## Commands to run on your GS PDF

Use your actual PDF path (e.g. in Downloads).

**1. Extract to JSON (first 5 pages, broker/tax prompt):**
```bash
python -m extract_vl "C:\Users\mwzah\Downloads\YOUR_GS_STATEMENT.pdf" --max-pages 5 --schema-type broker_statement --json output/statement_gs.json
```

**2. Convert JSON to Excel (QB-style sheet names from config):**
```bash
python run.py from-json output/statement_gs.json -o output/statement_gs.xlsx
```

**3. (Optional) Also write Excel from extract_vl in one go:**  
If you pass `--out`, extract_vl writes JSON only; use step 2 to get Excel. Or use the app (if you use it) which can do both.

---

## Config (Phase 2)

- **`config/vl.json`**  
  - `page_to_sheet`: map page number → sheet name (e.g. 3 → "Overview", 4 and 5 → "US Tax Summary").  
  - Edit this to change sheet names or add more pages; no code change.

---

## Next steps (from the plan)

- **Phase 1 (ongoing):** On your GS PDF, run the commands above and check that Overview, US Tax Summary, Reportable Interest, blanks, and no duplicated rows look correct. If not, tune prompts/post-process in `extract_vl.py`.
- **Phase 3:** PLSummary block structure (BOM/MTD/EOM columns, row mapping) — implement when Phase 1 is good.
- **Phase 5:** Journal Entry Import (account mapping + journal generation).
- **Optional:** Run benchmark: `pip install -r requirements-benchmark.txt`, then `python scripts/run_benchmark_eval.py --max-samples 10 --schema-type universal` (see REMINDER_NEXT_SESSION.md for HF cache note on Windows).

