# PDF corpus testing (local, private)

Use a **folder of real PDFs on your machine** to regression-test extraction. **Do not commit** customer or personal statements to the repository; `*.pdf` is gitignored, but keep corpus paths outside the repo if you prefer.

## What we improved (structure)

- **Ragged tables**: Rows from pdfplumber, Tabula, Camelot, or VL sometimes had **fewer or more cells** than the header row. The pipeline now **aligns** each section matrix to a **common width** (pad with empty cells; use max column count across rows) before JSON validation and Excel export.
- **Validation**: `evaluate_extraction_json_correctness` **realigns** rows and **rebuilds** the optional header grid (`column_headers` / `row_headers` / `data`) so it always matches the `rows` matrix.

This raises **quality_score** and reduces **failed** status for broker-style PDFs where the issue was **shape** mismatch, not missing content.

## Batch check script

From the project root:

```bash
export PDF_CORPUS_DIR="$HOME/Downloads/PDFs"
python scripts/run_pdf_corpus_check.py
```

Or:

```bash
python scripts/run_pdf_corpus_check.py "$HOME/Downloads/PDFs" --max-pages 12
```

- `--max-pages N` — faster smoke (first N pages only).
- `--json-out reports/corpus.json` — optional machine-readable summary (filenames + scores only, no cell data).

Exit code **0** if no file ends with validation status `failed`; **1** otherwise.

## Automated tests

Unit tests use **synthetic** tables only (`tests/test_tables_to_excel.py`). Run:

```bash
pytest tests/ -q
```

## Roadmap (optional)

- **Document-type presets**: tax (1099) vs brokerage — different column rules and prompts.
- **Golden JSON snapshots** (redacted) for CI — store **hashes** or anonymized excerpts, not raw PDFs.
- **Hybrid routing**: row-alignment is now less noisy; revisit **VL** thresholds if you want fewer bad-page reroutes.
