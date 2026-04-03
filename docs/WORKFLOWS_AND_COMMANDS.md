# PDF–Excel Tool: Workflows and Commands

**Reference document** for pdf-excel v3.2 — what you can run, and what to use by default.

**Generated for:** operators and developers  
**See also:** `docs/WHICH_COMMAND.md`, `README.md`, `config/README.md`

---

## One default (start here)

For most **text-based PDFs**:

- **CLI:** `python run.py tables path/to/file.pdf`
- **Web:** open the app, choose **Library + QB**, upload the PDF.

You get **Excel + JSON**. Check **`meta`** in the JSON for validation, audit (if enabled), and **library routing** (candidate pages for hybrid/VL).

---

## CLI commands (`python run.py …`)

There are **11** subcommands.

| Command | Role |
|---------|------|
| **tables** | PDF → library extract → QB-style **Excel** (+ JSON with audit + `library_routing`). Main path. |
| **hybrid** | Library first, then **VL only on flagged pages** → JSON (optional `--excel`). |
| **json** | PDF → **JSON only** (library). |
| **audit-json** | **Existing JSON + PDF** → audit report (no new extraction). |
| **from-json** | **JSON → Excel** (no PDF). |
| **clean-json** | Clean repetitive sections in a JSON file (optional `--pdf`). |
| **populate-template** | PDF → QB workbook → **fill your template .xlsx**. |
| **populate-template-from-fields** | **fields.json** + template → filled workbook (no PDF in this step). |
| **fields** | PDF → **structured fields JSON**. |
| **ask** | PDF + **query** → Excel via **Anthropic** or **smollm** (Q&A style, not full tables). |

**PDF as primary input:** tables, hybrid, json, audit-json (with PDF), populate-template, fields, ask.

---

## Web app (`flask --app app run`)

| Route | Purpose |
|-------|---------|
| **GET /** | Upload forms. |
| **POST /extract** | PDF → Library / Hybrid / Vision-only, or Ask AI → ZIP or xlsx. |
| **POST /pdf-to-json** | PDF → JSON ZIP (library / hybrid / VL). |
| **POST /json-to-excel** | JSON file → Excel (no PDF). |

---

## What to read in JSON `meta`

| Area | Fields (typical) |
|------|-------------------|
| **Structure** | `status`, `validation_errors`, `validation_warnings`, `quality_score` — from `evaluate_extraction_json_correctness()` in `tables_to_excel.py` (library `_write_json_from_sections`, VL `pdf_to_json_vl`, hybrid merged output, and hybrid “no VL” branch). |
| **PDF vs JSON** | `audit_summary` (pass/fail, confidence, scope) when audit ran |
| **Library → hybrid hint** | `library_routing.candidate_vl_pages`, `hybrid_recommended`, `recommended_action` |

**Correctness vs PDF:** audit summary.  
**Whether to try hybrid:** `library_routing` (no need to run three pipelines blindly).

---

## Extraction modes (how JSON is produced)

- **Library only** — fast, text PDFs; no VL.
- **Hybrid** — same library pass, VL **only** on pages flagged by heuristics.
- **Vision-only** — every page through VL (slow; scans).

Hybrid does **not** use VL to *find* bad pages; it uses **library output** first, same as `library_routing` on a `tables` run.

---

## Optional / dev

- **`scripts/`** — model download, JSON compare, benchmarks, etc.
- **`tables_to_excel.py` as main** — alternate direct CLI to xlsx.

---

## Version

Bundled with **pdf-excel** branch **v3.2** (see `VERSION`).
