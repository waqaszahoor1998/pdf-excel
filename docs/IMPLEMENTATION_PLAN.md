# Implementation plan (for later)

This file captures the agreed roadmap: extractor contract, validator/scoring, hybrid routing, typed fields, benchmarking, and GitHub timing. **Not implemented yet** — reference when you continue work.

---

## Extractor contract (what “contract” means)

The **contract** is the guaranteed shape and meaning of extraction JSON:

- **Stable structure** for every run: `sections` + `meta` (+ optional extras).
- **Clear status**: what “ok” vs “requires review” vs “failed” means.
- **Auditability**: what ran, quality, warnings/errors.

### Suggested top-level JSON

- **`sections`**: list of blocks/tables (`name`, `headings`, `rows`, optional `page`).
- **`meta`**: required metadata + validation outcomes.
- **`meta.status`**: `ok` | `requires_review` | `failed` (or equivalent).
- **`meta.requires_review`**: boolean (downstream can trust this).
- **`meta.quality_score`**: 0–1 (document-level).
- **`meta.warnings` / `meta.errors`**: machine-readable messages.
- If hybrid/VL used: which pages routed, timings, chosen source (per existing hybrid meta patterns).

### Status rules (suggested)

- **`failed`**: unreadable/encrypted PDF, invalid file, unrecoverable error.
- **`requires_review`**: validator says low quality or structural issues.
- **`ok`**: validator passes and quality ≥ threshold.

---

## Milestone 1 — Contract + real validator/scoring (do this first)

### Validator outputs

- **Document-level**: `quality_score`, `requires_review`, `warnings[]`, `errors[]`, optional `recommended_action` (`use_library`, `try_hybrid`, `try_vl`, `reject`).
- **Per-page** (optional first phase): `page_scores`, `page_reasons`.

### Signals to score (start simple, expand)

- Table-like ratio, structured row ratio, null-heavy ratio, prose-heavy ratio.
- Fragmentation / noisy section names.
- Column consistency (existing column mismatch detection).

### Hard gates (fail-closed)

- Invalid JSON schema for extraction payload.
- No sections on a multi-page PDF (or similar sanity checks).
- Too many structural errors (tune threshold).

### Wiring

- **`run.py json`**: after extract → validator → merge into `meta`.
- **`pdf_to_qb_excel` / `run.py tables`**: same `meta` on written JSON.
- **`run.py fields`**: include validator summary or point to same contract.

### Tests

- Unit tests: synthetic good/bad sections.
- Regression on one real PDF when available.

---

## Milestone 2 — Tight hybrid routing

- Route to VL only when validator/page score says so (align with `docs/HYBRID_ROUTING.md` logic).
- Production limits: `max-pages`, `max-vl-pages`, timeouts.
- **Always** record in JSON `meta`: routed pages, reasons, timings, merge decisions.

---

## Milestone 3 — Typed fields as primary “useful data” layer

- Expand `run.py fields` / `fields.json` with a minimal universal field set (period, accounts, key totals, cash, etc.).
- Provenance + confidence on every field.
- Optional: required-field sets per document class (broker vs tax vs …).
- Cross-checks where possible (totals, BOM/EOM).

---

## Milestone 4 — Benchmarking

- Curate 10–30 PDFs across layouts.
- Script: run extract + fields + validator → summary table (% ok / requires_review / failed, scores, latency).
- Use results to tune thresholds and hybrid routing.

---

## GitHub / push timing

- **Recommended**: push **after Milestone 1** is done and tests pass (one coherent “service-grade” boundary).
- Alternative: push now if you need backup; expect follow-up commits for contract + validator.

---

## Order of work (summary)

1. Extractor contract fields in JSON (`meta.status`, `requires_review`, `quality_score`, warnings/errors).
2. Validator + scoring module + tests + wire into `run.py json` (and JSON from `tables`/`pdf_to_qb_excel`).
3. Hybrid routing tightened + limits + meta audit.
4. Typed fields expansion + cross-checks.
5. Benchmark harness + dataset.

---

## Reference commands (demo / recording)

- `python run.py json <pdf> -o output\extraction.json`
- `python run.py from-json output\extraction.json -o output\from_json.xlsx`
- `python run.py tables <pdf> -o output\qb.xlsx`
- `python run.py fields <pdf> -o output\fields.json`
- Hybrid (optional, slower): `python run.py hybrid <pdf> -o output\hybrid.json --schema-type broker_statement --excel`

---

*Last captured from project discussion — implement when ready.*
