# Extraction evaluation — diverse PDF forms

This folder supports a **broader** view than broker-only PDFs: government forms, academic papers, and synthetic samples. The goal is to see **how** the library pipeline behaves on different layouts, then **prioritize** changes (shared heuristics vs. document-type profiles vs. hybrid/VL).

## What gets tested

For every PDF in `public_pdfs/`, the evaluator runs the same path as the web app’s **library** mode:

`pdf_to_qb_excel` → canonical JSON → `evaluate_extraction_json_correctness` → schema validation → short **PDF-vs-JSON audit** (page cap).

Metrics include **pages**, **sections**, **row count**, **QC status/score**, and **category** (from `corpus.json`).

## Corpus (`corpus.json`)

`evaluation/corpus.json` lists each file with:

- **`category`** — e.g. `synthetic_broker_like`, `government_form`, `academic_two_column`, `academic_single_column`, `sec_structured_form`
- **`url`** — optional; used by the downloader
- **`note`** — how to interpret scores (e.g. academic papers often “fail” QC without meaning the broker path is broken)

**Add more PDFs** by appending an object with `file`, `url`, `category`, and `note`, then run the downloader.

## Commands

```bash
# 1) Fetch PDFs listed in corpus.json (best effort; some sites block bots)
python scripts/download_eval_pdfs.py
# or: python scripts/download_eval_pdfs.py --force

# 2) Run evaluation on everything in evaluation/public_pdfs/*.pdf
python scripts/evaluate_public_pdfs.py

# 3) Read outputs
cat evaluation/results/last_eval.md
```

Outputs (under `evaluation/results/`, gitignored):

- **`last_eval.json`** — machine-readable
- **`last_eval.md`** — table + corpus notes

## Interpreting results (toward “more universal” extraction)

- **Same codebase** cannot be optimal for tax forms, PLDI papers, and broker statements at once. **Universal** usually means: robust table detection, good sectioning, honest validation — not identical Excel shape for every genre.
- **Low QC on academic / government** often reflects **ragged or non-tabular** layout, not a single bug. Improvements might be: skip narrative pages, multi-column detection, or **routing** to hybrid/VL when the library score is poor.
- **Broker PDFs** — add your own anonymized samples to `public_pdfs/` and extend `corpus.json`; those drive the most valuable product fixes.

## Committed vs. downloaded files

- **`generated_sample_report.pdf`** is small and **committed** (smoke test).
- Other corpus PDFs are **gitignored** — run `download_eval_pdfs.py` locally or drop files in manually (e.g. SEC template if curl gets 403).

## CI

Run `python scripts/evaluate_public_pdfs.py` locally or in nightly jobs; `tests/test_evaluate_public_pdfs_smoke.py` only checks the tiny generated sample.
