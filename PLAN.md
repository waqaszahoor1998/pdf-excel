# PDF → Excel — Full project plan (A to Z)

This is the **complete** plan. Nothing is rushed; each step is done properly before moving on. We check everything so it works as intended.

---

## 1. Project goal (what we’re building)

- **Input:** PDFs with mixed content (tables, text, charts).
- **Output:** Excel file(s) (.xlsx) with the data the user cares about.
- **Two paths:**
  1. **Without AI (offline):** Extract **all** tables from a PDF into one Excel file. No API key; data never leaves the machine.
  2. **With AI (Anthropic):** User asks in natural language (e.g. “company taxes for January 2026”) → AI finds that part → we return only that as Excel. Uses Anthropic API key; data is not used for training (see Confidentiality below).
- **Confidentiality:** For data that must never leave the machine, use only the non-AI path. When using the API, Anthropic does not use your data for training; data is sent over HTTPS and retained only temporarily. See README “Confidentiality & privacy”.

---

## 2. Prerequisites (before any development)

Everything that must be in place before we rely on it.

| # | Prerequisite | Check |
|---|--------------|--------|
| P.1 | **Python 3.10+** installed and on PATH | `python3 --version` (or `py -3 --version` on Windows). |
| P.2 | **pip** available | `pip --version` or `python3 -m pip --version`. |
| P.3 | **Project folder** exists and is the working root | e.g. `pdf-excel/` with no conflicting names. |
| P.4 | **Anthropic account** (for AI path only) | Ability to create an API key at [console.anthropic.com](https://console.anthropic.com/). |
| P.5 | **Sample PDFs** for testing | At least 2–3 real PDFs: one with clear tables, one with mixed layout, one edge case (e.g. many pages or no tables). |
| P.6 | **Git** (optional but recommended) | So we can track changes and roll back if needed. |

**Sign-off:** All of the above confirmed before starting Phase 1.

---

## 3. Phase 0 — Already done (current state)

What exists today. No action unless we find a gap.

| # | Task | Status |
|---|------|--------|
| 0.1 | Project folder and `requirements.txt` (anthropic, openpyxl, python-dotenv, pdfplumber) | Done |
| 0.2 | Non-AI path: `tables_to_excel.py` (pdfplumber → all tables → Excel) | Done |
| 0.3 | AI path: `extract.py` (PDF + query → Anthropic → CSV → Excel) | Done |
| 0.4 | `.env.example` and `.gitignore` (e.g. `.env`, `__pycache__/`, `*.xlsx` in output dir if desired) | Done |
| 0.5 | README: usage, how the AI agent works, confidentiality, Anthropic setup | Done |
| 0.6 | This plan document | Done |

**Before Phase 1:** Re-read README and this plan; confirm nothing in Phase 0 is missing for your team.

---

## 4. Phase 1 — Validate and harden (foundation)

Goal: Make sure both scripts work correctly on real PDFs and fail clearly when something is wrong. No new features yet.

### 4.1 Non-AI path (`tables_to_excel.py`)

| # | Task | Details | Done |
|---|------|--------|------|
| 1.1 | Run on 2–3 real PDFs | Different layouts: simple table, multi-page, multiple tables per page. Open the generated .xlsx and confirm: sheets exist, headers and data look correct, no missing/corrupt cells. | [ ] |
| 1.2 | Test edge cases | (a) PDF with **no tables** — script should not crash; either create one empty sheet or exit with a clear message. (b) **Empty or corrupt PDF** — clear error, no traceback to user. (c) **Non-PDF file** — reject with clear message. | [ ] |
| 1.3 | Fix extraction if needed | If tables are missed or merged wrong, tune pdfplumber (e.g. `extract_tables(table_settings={...})` or different strategy). Document any layout that doesn’t work well. | [ ] |
| 1.4 | File and path edge cases | (a) Path with spaces. (b) Output path to a read-only or non-existent parent dir — clear error. (c) Output path already exists — decide: overwrite or require a flag / different path, then implement. | [ ] |

### 4.2 AI path (`extract.py`)

| # | Task | Details | Done |
|---|------|--------|------|
| 1.5 | Run with real PDF + query (with API key) | Use a PDF that clearly contains the requested data. Confirm: Excel is created, content matches the requested section, headers and rows are correct. | [ ] |
| 1.6 | Test API and parsing edge cases | (a) **Missing or invalid API key** — clear error (no raw key in message). (b) **API error** (e.g. rate limit, timeout) — catch and report clearly. (c) **Model returns no CSV block** — current fallbacks (markdown, first comma line); if still failing, improve error message and optionally retry or ask user to rephrase. | [ ] |
| 1.7 | PDF size and format | (a) PDF **over 32 MB** — reject before calling API with clear message. (b) **Password-protected PDF** — reject or document as unsupported. (c) **Very long PDF** (e.g. 50+ pages) — document expected behaviour (slower, possible token limits). | [ ] |
| 1.8 | Query edge cases | (a) Query matching **nothing** in PDF — agent should return “no matching data” row or similar; we write that to Excel and don’t crash. (b) Very long query — no crash. | [ ] |

### 4.3 Errors and exit codes

| # | Task | Details | Done |
|---|------|--------|------|
| 1.9 | Consistent error messages | All user-facing errors: short, clear, no stack trace unless in debug mode. | [ ] |
| 1.10 | Exit codes | Success: 0. Failure: non-zero (e.g. 1). Scripts are scriptable (e.g. `if python extract.py ...; then ...`). | [ ] |

### 4.4 Documentation

| # | Task | Details | Done |
|---|------|--------|------|
| 1.11 | Document PDF limits and quirks | In README: max size (32 MB for API path), page limits (100 for API), unsupported (password-protected, scanned/OCR if we don’t support it), and any known layout limitations from 1.3. | [ ] |

**Phase 1 sign-off:** All 1.1–1.11 done; both scripts run correctly on the chosen test PDFs and fail in a predictable way. No unchecked boxes before moving to Phase 2.

---

## 5. Phase 2 — Structure and quality

Goal: Consistent behaviour, easier maintenance, and a base for future features.

### 5.1 Output and paths

| # | Task | Details | Done |
|---|------|--------|------|
| 2.1 | Output path behaviour | Document clearly: default output path (e.g. same name as PDF with .xlsx, same directory). `-o` overrides. If output dir doesn’t exist, create it (already done in code; confirm and document). | [ ] |
| 2.2 | Optional: default output directory | e.g. always write to `output/` unless `-o` is set. If we add this, document and keep it consistent across both scripts. | [ ] |

### 5.2 Configuration (optional)

| # | Task | Details | Done |
|---|------|--------|------|
| 2.3 | Optional config file | e.g. `config.yaml` or `.env` entries: default model, default output dir. Not required for MVP; add only if it simplifies usage. | [ ] |

### 5.3 Logging and observability

| # | Task | Details | Done |
|---|------|--------|------|
| 2.4 | Logging instead of only print | Use Python `logging`. At minimum: which PDF, which query (for extract), output path, and errors. Level configurable (e.g. INFO by default, DEBUG for development). | [ ] |
| 2.5 | No secrets in logs | Ensure API key and file contents are never logged. | [ ] |

### 5.4 Tests (optional but recommended)

| # | Task | Details | Done |
|---|------|--------|------|
| 2.6 | Unit tests for extraction helpers | For `extract.py`: test `extract_csv_from_response()` with sample responses (ideal CSV block, markdown block, malformed). Test `csv_to_excel()` with valid CSV and edge cases (empty, single row, commas in cells). | [ ] |
| 2.7 | Unit tests for tables_to_excel (optional) | If we have a tiny fixture PDF or mock pdfplumber output, test that we produce the expected sheet names and row count. | [ ] |
| 2.8 | Test runner | e.g. `pytest`. Document how to run tests (`pytest` or `python -m pytest`). | [ ] |

**Phase 2 sign-off:** Output behaviour is documented and consistent; logging is in place and safe; tests (if added) pass. No unchecked boxes before Phase 3.

---

## 6. Phase 3 — UX and scale

Goal: Easier to use day-to-day and ready for multiple files or heavier use.

### 6.1 CLI structure

| # | Task | Details | Done |
|---|------|--------|------|
| 3.1 | Unified entry point (optional) | e.g. `python run.py tables document.pdf` vs `python run.py ask document.pdf "query"`. Both modes documented. Alternatively keep two scripts and document both clearly. | [ ] |
| 3.2 | Help and usage | `--help` for every script; examples in README for both paths. | [ ] |

### 6.2 Batch and progress

| # | Task | Details | Done |
|---|------|--------|------|
| 3.3 | Batch: multiple PDFs | e.g. `python tables_to_excel.py dir/` or `python tables_to_excel.py a.pdf b.pdf` → one Excel per PDF (or one combined; decide and document). Same for `extract.py` if we support batch (e.g. same query for many PDFs). | [ ] |
| 3.4 | Progress / status | For long PDFs: e.g. “Page 3/20” for tables_to_excel; “Calling API…”, “Done.” for extract. Avoid flooding the console; one line or simple spinner is enough. | [ ] |

### 6.3 API efficiency (optional)

| # | Task | Details | Done |
|---|------|--------|------|
| 3.5 | Anthropic Files API | Upload PDF once, get `file_id`; reuse for multiple queries on the same PDF. Reduces re-upload and can speed up repeated extractions. | [ ] |

**Phase 3 sign-off:** CLI is clear and documented; batch (if added) works; progress (if added) is clear. No unchecked boxes before Phase 4.

---

## 7. Phase 4 — AI behaviour (agents)

Goal: More reliable and flexible AI extraction.

### 7.1 Prompts and output format

| # | Task | Details | Done |
|---|------|--------|------|
| 4.1 | Refine system prompt | Few-shot examples in the prompt; stricter rules for CSV (escaping, headers). Decide: “one table only” vs “all matching tables” and document. | [ ] |
| 4.2 | Multiple tables in one run | If user asks for “all tax tables”, support returning several CSV blocks or one Excel with multiple sheets. Define format and implement parsing. | [ ] |
| 4.3 | Structured output (if available) | If Anthropic supports JSON schema / structured output for the table, use it to avoid parsing CSV from free text. | [ ] |
| 4.4 | Long PDFs (optional) | Optional “summarize then extract” flow: first ask for document structure/sections, then extract by section to stay within token limits. | [ ] |

**Note:** All AI features use **Anthropic** only. API key in `.env` as `ANTHROPIC_API_KEY`. See README “How we use Anthropic”.

**Phase 4 sign-off:** Extraction quality and multi-table (if implemented) verified on real PDFs. No unchecked boxes before Phase 5.

---

## 8. Phase 5 — Interface (optional)

Only if we want something beyond the CLI.

| # | Task | Details | Done |
|---|------|--------|------|
| 5.1 | Minimal web UI | Upload PDF, text box for query (AI path), button to run, download resulting Excel. Auth and hosting are separate decisions. | [ ] |
| 5.2 | Or: local GUI | e.g. Tkinter or PyQt: choose PDF, enter query, choose output path, run. | [ ] |
| 5.3 | Or: API for another app | REST or internal API that wraps `tables_to_excel` and `extract_pdf_to_excel`; API key or auth as needed. | [ ] |

**Phase 5 sign-off:** Chosen option works end-to-end and is documented.

---

## 9. What we’re not doing (out of scope, unless we decide otherwise)

- **Other AI providers:** Plan is Anthropic-only unless we explicitly add another.
- **OCR / scanned PDFs:** Treated as out of scope unless we add a dedicated step (e.g. OCR then extract).
- **Editing PDFs:** We only read and extract; we don’t modify PDFs.
- **Real-time / streaming:** Extraction is request/response; no streaming of partial results in the current plan.

---

## 10. Dependencies and environment (reference)

- **Python:** 3.10+.
- **Libraries:** anthropic, openpyxl, python-dotenv, pdfplumber (see `requirements.txt`). Pin versions for reproducibility if needed (e.g. in production).
- **Env vars:** `ANTHROPIC_API_KEY` for AI path only; loaded from `.env` via python-dotenv.
- **OS:** Scripts should work on macOS, Linux, and Windows (paths and CLI tested on at least one of each if we claim support).

---

## 11. Security and confidentiality (reference)

- **Offline path:** No network; data never leaves the machine. Use for highly confidential PDFs.
- **API path:** Data sent to Anthropic over HTTPS; not used for training; retained only temporarily (e.g. 30 days). See README “Confidentiality & privacy”.
- **Secrets:** API key only in `.env`; `.env` in `.gitignore`; never log or print the key.

---

## 12. Summary checklist (order of work)

- [ ] **Prerequisites (Section 2):** All checks done.
- [ ] **Phase 1:** Validate and harden (Section 4) — every 1.x task done and signed off.
- [ ] **Phase 2:** Structure and quality (Section 5) — every 2.x task done and signed off.
- [ ] **Phase 3:** UX and scale (Section 6) — every 3.x task done and signed off.
- [ ] **Phase 4:** AI behaviour (Section 7) — every 4.x task done and signed off.
- [ ] **Phase 5 (optional):** Interface (Section 8) — if we do it, every 5.x done and signed off.

---

## 13. Next step

**Start with Prerequisites (Section 2):** Confirm Python, pip, project folder, Anthropic account (if using AI), and that you have 2–3 sample PDFs. Then begin **Phase 1, Task 1.1**: run `tables_to_excel.py` on those PDFs and note exactly what works and what doesn’t.

When you’re ready, say which task you’re on and we’ll do it step by step.
