# How much we did and what to do next

Keep in mind: **do everything** in the plan. This file summarizes progress and the remaining work.

---

## Done so far

### Phase 0 — Setup
- Repo on GitHub, `requirements.txt`, `.env.example`, `.gitignore`, README, PLAN, BRANCHING.
- **v1** branch and **v1.0.0** tag.

### Phase 1 — Validate and harden
- **1.2** Edge cases: no tables → “Info” sheet; corrupt/empty/non-PDF → clear errors; password-protected → clear message.
- **1.4** Paths and overwrite: `--no-overwrite`; output dir created; overwrite by default.
- **1.6** API/parsing: missing key, rate limit, overload → clear messages; no key in output.
- **1.7** PDF limits: 32 MB rejected; password-protected rejected; documented.
- **1.8** Query edge cases: “no matching data” row; long query doesn’t crash.
- **1.9** Error messages and exit codes: 0/1; scriptable.
- **1.10** README: PDF limits and quirks.
- **Still for you:** 1.1 (run on 2–3 real PDFs), 1.3 (tune extraction if needed), 1.5 (real PDF + query with API key).

### Phase 2 — Structure and quality
- **2.1** Output path behaviour documented in README.
- **2.3** Logging in both scripts; no secrets.
- **2.5** Unit tests for `extract.py` (CSV parsing, Excel write).
- **2.6** pytest; “Running tests” in README.
- **Skipped (optional):** 2.2 default output dir, 2.4 config file.

### Phase 3 — UX and scale
- **3.1** Single entry: `run.py tables` and `run.py ask`.
- **3.2** `--help` and README examples (including run.py).
- **3.3** Batch: multiple PDFs and/or directory → one Excel per PDF (tables and ask).
- **3.4** Progress: “Page N/total” in tables; “Calling API…”, “Done.” in extract.
- **Not done:** 3.5 Anthropic Files API (optional).

---

## What to do next (in order)

1. **Phase 4 — AI behaviour**
   - **4.1** Refine system prompt (few-shot, stricter CSV).
   - **4.2** Multiple tables in one run → multiple sheets.
   - **4.3** (Optional) Structured output (JSON) if Anthropic supports it.
   - **4.4** (Optional) Long PDFs: “summarize then extract”.

2. **Phase 5 — Interface (optional)**
   - **5.1** Web UI (upload PDF, query, download Excel), or  
   - **5.2** Local GUI (e.g. Tkinter), or  
   - **5.3** REST API (for n8n and others).

3. **Your checks**
   - Run `tables_to_excel.py` / `run.py tables` on 2–3 real PDFs (Phase 1.1).
   - Run `extract.py` / `run.py ask` with a real PDF + query and API key (Phase 1.5).

---

## Quick reference

| Phase | Status | Remaining |
|-------|--------|-----------|
| 0 | Done | — |
| 1 | Done (code); you test with real PDFs | 1.1, 1.3, 1.5 |
| 2 | Done | 2.2, 2.4 (optional) |
| 3 | Done | 3.5 (optional) |
| 4 | Not started | 4.1, 4.2, 4.3, 4.4 |
| 5 | Not started | 5.1 or 5.2 or 5.3 |

See **PLAN.md** for the full task list and checkboxes.
