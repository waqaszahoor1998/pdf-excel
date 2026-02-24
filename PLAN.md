# PDF → Excel: Elaborate project plan

This plan covers everything we need **before and during** building the PDF-to-Excel converter with AI agents. We do not rush; each step is done properly. Clean-up and research are reflected below.

---

## 0. Clean-up and repo (done)

| Item | Status |
|------|--------|
| Remove `GITHUB_SETUP.md` (no longer needed after repo is created) | Done |
| Code lives on GitHub: `waqaszahoor1998/pdf-excel` | Done |

---

## 1. Project goal (what we’re building)

We need **two layers**, in order:

**1. Foundation: a PDF-to-Excel converter (backend).**  
First we build the code that can take a PDF and produce Excel — reading the PDF, extracting table data, writing .xlsx. That’s backend programming: it has to work reliably. Today that’s the offline path (e.g. pdfplumber → all tables → Excel) and the plumbing for “table data → Excel”. This is the base the rest sits on.

**2. End goal: implement the AI agent in that.**  
Our main product direction is the **AI agent**: the user gives a PDF and says in natural language what they need (e.g. “company taxes for January 2026”); the system figures out *what* to extract and then uses the same converter to produce Excel. So we’re not “AI agent only” from day one — we get a solid PDF→Excel converter first, then we **add** the AI agent on top. The AI agent is the “brain” (Claude) that decides which part of the PDF to extract; the converter is the “engine” that turns that into Excel.

- **Right now:** We have a working converter (offline: all tables → Excel) and an AI path (PDF + query → Claude → table → Excel). We keep improving the converter and the AI integration.
- **Offline mode:** No AI, no API; extracts all tables. Good for confidentiality or when you don’t want to use the API. Part of the converter foundation.
- **Confidentiality:** Offline = no network. AI path = Anthropic only; data not used for training; sent over HTTPS, retained only temporarily. See README “Confidentiality & privacy”.

---

## 2. Research summary (what we can learn from)

### 2.1 Market and best practices

- **IDP market:** Intelligent document processing is growing (e.g. ~$2B by 2026); many vendors; adoption still early. Manual data entry is costly (e.g. $28K+ per employee/year); automation can yield large time savings and fewer re-entries.
- **AI extraction:** Modern AI can reach very high field-level accuracy (e.g. 98–99%) vs traditional OCR (~60–70%). Strong solutions combine OCR, computer vision, and LLMs with validation and confidence scoring.
- **Best practices:** Start small and iterate; treat security and compliance seriously; keep human oversight where accuracy or compliance matter; assess ROI (e.g. 50+ PDFs/week or month-end impact).

### 2.2 Features others offer (ideas for later)

- Multi-page table detection and reconstruction.
- Semantic understanding (e.g. “Subtotal”, “VAT”).
- Mixed content: tables, paragraphs, scanned pages.
- Anomaly detection and line-by-line structuring.
- API integrations and direct export to Excel/JSON.
- Confidence scores and human-in-the-loop review for low-confidence extractions.

### 2.3 PDF and table extraction challenges

- **Digital vs scanned:** We currently focus on digital/text-based PDFs. Scanned PDFs need OCR (out of scope until we add it).
- **Table complexity:** Cross-column/cross-row layouts, wireless tables, multi-line cells, missing cells. Rule-based tools (Tabula, Camelot, pdfplumber) can struggle on complex layouts; we use pdfplumber and can add Camelot or other backends later if needed.
- **Format limits:** Password-protected PDFs unsupported; API path has size (e.g. 32 MB) and page (e.g. 100) limits.

### 2.4 Tool comparison (reference)

- **pdfplumber (current):** Good for machine-generated PDFs; table extraction + layout; no OCR. We use this for the offline path.
- **Camelot:** Lattice/stream modes; quality metrics; Excel/CSV export; text-based PDFs only. Possible addition for difficult tables.
- **Tabula:** Similar use cases; Camelot often compared favourably for lattice tables.
- **AI (Claude):** Handles complex layouts and natural-language selection; requires API and sends data to Anthropic.

---

## 3. Who we’re building for (personas)

| Persona | Need | How we serve them |
|--------|------|-------------------|
| **Analyst / ops** | “I have a long PDF and only need one section (e.g. January taxes) in Excel.” | **AI agent** (end goal). |
| **Compliance / confidential** | “Data must not leave our network.” | **Converter offline mode** (no AI, no API). |
| **Power user / scripted** | “I want to batch many PDFs or integrate into a pipeline.” | CLI (converter + AI agent when ready); later batch and optional API. |
| **Casual user** | “I want to upload a PDF and get Excel without the command line.” | Future: web or desktop UI (Phase 5) on top of the converter and **AI agent**. |

---

## 4. Success criteria (what “done” looks like)

- **Phase 1:** Both scripts run correctly on real PDFs; edge cases (no tables, bad file, API errors) are handled with clear messages and exit codes; limits and quirks documented.
- **Phase 2:** Output behaviour and logging are consistent; no secrets in logs; optional tests in place and passing.
- **Phase 3:** CLI (and optional batch) is clear and documented; progress feedback for long runs where useful.
- **Phase 4:** AI extraction is reliable; prompt and output format (single/multi-table) are defined and documented.
- **Phase 5 (if we do UI):** Chosen interface (web/GUI/API) works end-to-end and is documented.
- **Ongoing:** README and this plan stay accurate; team can onboard and run the tool from the repo.

---

## 5. Prerequisites (before Phase 1)

| # | Prerequisite | Check |
|---|--------------|--------|
| P.1 | Python 3.10+ on PATH | `python3 --version` (or `py -3 --version` on Windows). |
| P.2 | pip available | `pip --version` or `python3 -m pip --version`. |
| P.3 | Project root is the repo folder | e.g. `pdf-excel/` with no name conflicts. |
| P.4 | Anthropic account (for AI path) | Can create API key at [console.anthropic.com](https://console.anthropic.com/). |
| P.5 | Sample PDFs for testing | At least 2–3: clear tables, mixed layout, one edge case (e.g. no tables or many pages). |
| P.6 | Git (recommended) | For version control and pushing to GitHub. |

**Sign-off:** All above confirmed before starting Phase 1.

---

## 6. Phase 0 — Current state (done)

| # | Task | Status |
|---|------|--------|
| 0.1 | `requirements.txt`: anthropic, openpyxl, python-dotenv, pdfplumber | Done |
| 0.2 | Non-AI path: `tables_to_excel.py` | Done |
| 0.3 | AI path: `extract.py` (Anthropic, PDF + query → Excel) | Done |
| 0.4 | `.env.example`, `.gitignore`, README, confidentiality notes | Done |
| 0.5 | This plan; repo on GitHub | Done |

---

## 7. Phase 1 — Validate and harden (foundation)

Goal: Both scripts work on real PDFs and fail in a clear, predictable way. No new features.

### 7.1 Non-AI path (`tables_to_excel.py`)

| # | Task | Details | Done |
|---|------|--------|------|
| 1.1 | Run on 2–3 real PDFs | Different layouts; confirm sheets, headers, and data in generated .xlsx. | [ ] |
| 1.2 | Edge cases | No tables → no crash; clear message or single empty sheet. Empty/corrupt/non-PDF → clear error. | [ ] |
| 1.3 | Fix extraction if needed | Tune pdfplumber settings if tables are missed or wrong; document layouts that don’t work well. | [ ] |
| 1.4 | Paths and overwrite | Paths with spaces; read-only or missing output dir; overwrite vs require flag — decide and implement. | [ ] |

### 7.2 AI path (`extract.py`)

| # | Task | Details | Done |
|---|------|--------|------|
| 1.5 | Real PDF + query test | API key set; Excel created; content matches requested section. | [ ] |
| 1.6 | API and parsing edge cases | Missing/invalid key → clear error. Rate limit/timeout → catch and report. No CSV block → improve message/fallback. | [ ] |
| 1.7 | PDF limits | Over 32 MB → reject before API. Password-protected → reject or document. Long PDFs → document behaviour. | [ ] |
| 1.8 | Query edge cases | No match in PDF → “no matching data” row or message; don’t crash. Very long query → no crash. | [ ] |

### 7.3 Errors and docs

| # | Task | Details | Done |
|---|------|--------|------|
| 1.9 | Error messages and exit codes | User-facing errors short and clear; success 0, failure non-zero; scriptable. | [ ] |
| 1.10 | Document limits and quirks | README: max size, page limit, unsupported (e.g. password, scanned), known layout limits. | [ ] |

**Phase 1 sign-off:** All 1.1–1.10 done; both scripts validated on sample PDFs.

---

## 8. Phase 2 — Structure and quality

Goal: Consistent behaviour, maintainability, optional tests.

| # | Task | Details | Done |
|---|------|--------|------|
| 2.1 | Output path behaviour | Document default and `-o`; create output dir if needed. | [ ] |
| 2.2 | Optional default output dir | e.g. `output/` unless `-o` set; document. | [ ] |
| 2.3 | Logging | Use `logging`; log PDF, query (extract), output path, errors; no secrets. | [ ] |
| 2.4 | Optional config | e.g. default model, output dir in `.env` or config file. | [ ] |
| 2.5 | Unit tests (optional) | `extract.py`: CSV parsing and Excel write; optionally `tables_to_excel` with fixture/mock. | [ ] |
| 2.6 | Test runner | e.g. pytest; document how to run. | [ ] |

**Phase 2 sign-off:** Output and logging consistent; tests (if added) pass.

---

## 9. Phase 3 — UX and scale

Goal: Easier daily use and batch use.

| # | Task | Details | Done |
|---|------|--------|------|
| 3.1 | CLI structure | Optional single entry (e.g. `run.py tables` / `run.py ask`) or keep two scripts; document. | [ ] |
| 3.2 | Help and examples | `--help` and README examples for both paths. | [ ] |
| 3.3 | Batch | Multiple PDFs → multiple Excel files (or one combined); document. | [ ] |
| 3.4 | Progress | e.g. “Page 3/20”, “Calling API…”, “Done.” for long runs. | [ ] |
| 3.5 | Anthropic Files API (optional) | Upload once, reuse `file_id` for multiple queries on same PDF. | [ ] |

**Phase 3 sign-off:** CLI and batch (if added) clear and documented.

---

## 10. Phase 4 — AI behaviour (agents)

Goal: More reliable and flexible AI extraction.

| # | Task | Details | Done |
|---|------|--------|------|
| 4.1 | System prompt | Few-shot examples; strict CSV rules; one table vs “all matching” defined. | [ ] |
| 4.2 | Multiple tables | Support several CSV blocks or multiple sheets in one Excel from one query. | [ ] |
| 4.3 | Structured output | If Anthropic supports JSON schema for tables, use it to avoid fragile CSV parsing. | [ ] |
| 4.4 | Long PDFs | Optional “summarize then extract” (structure first, then by section). | [ ] |

**Note:** AI = Anthropic only; key in `.env` as `ANTHROPIC_API_KEY`.

**Phase 4 sign-off:** Extraction quality and multi-table (if implemented) verified.

---

## 11. Phase 5 — Interface (optional)

Only if we want more than CLI.

| # | Task | Details | Done |
|---|------|--------|------|
| 5.1 | Web UI | Upload PDF, query box (AI path), run, download Excel. Auth/hosting separate. | [ ] |
| 5.2 | Or local GUI | e.g. Tkinter/PyQt: choose PDF, query, output path, run. | [ ] |
| 5.3 | Or API | REST/internal API wrapping both extraction paths; auth as needed. Enables **n8n** (and other tools) to call us via HTTP Request node. | [ ] |

**Phase 5 sign-off:** Chosen option works end-to-end and is documented.

---

## 11b. Using n8n (workflow automation)

We can use the converter and AI agent from [n8n](https://n8n.io) in two ways:

- **Execute Command node (self-hosted n8n only):** Run `python tables_to_excel.py ...` or `python extract.py ...` from an n8n workflow. The host/container must have Python and our dependencies; `ANTHROPIC_API_KEY` must be set for the AI path. Execute Command is disabled by default in n8n 2.0+ and not available on n8n Cloud. See README “Using with n8n”.
- **HTTP API (when we add it):** If we add a REST API (Phase 5), n8n can call it with the HTTP Request node (works with n8n Cloud if the API is reachable).

---

## 12. Future possibilities (not in current scope)

Ideas we can add later, not required to start:

- **OCR / scanned PDFs:** Run OCR (e.g. Tesseract, cloud) then extract tables; document as separate mode.
- **Alternative backends:** Camelot or Tabula for specific layouts where pdfplumber is weak.
- **Confidence and validation:** Confidence score per extraction; optional human-in-the-loop for low confidence.
- **Semantic labels:** Recognize “Subtotal”, “VAT”, etc., and map to consistent column names.
- **Export formats:** JSON, CSV, or SQLite in addition to Excel.
- **Other AI providers:** Only if we explicitly decide to support them.

---

## 13. Out of scope (unless we decide otherwise)

- Other AI providers (plan is Anthropic-only for AI).
- OCR/scanned PDFs (until we add a dedicated step).
- Editing or modifying PDFs (read and extract only).
- Real-time or streaming extraction (request/response only).

---

## 14. References

- **Dependencies:** Python 3.10+; anthropic, openpyxl, python-dotenv, pdfplumber (see `requirements.txt`). Env: `ANTHROPIC_API_KEY` in `.env`.
- **Security:** Offline = no network. API = HTTPS, not used for training, short retention. Never log or commit API key.
- **OS:** Target macOS, Linux, Windows (test on at least one of each if we claim support).

---

## 15. Summary checklist (order of work)

- [ ] Prerequisites (Section 5) confirmed.
- [ ] Phase 1 (Section 7) — validate and harden.
- [ ] Phase 2 (Section 8) — structure and quality.
- [ ] Phase 3 (Section 9) — UX and scale.
- [ ] Phase 4 (Section 10) — AI behaviour.
- [ ] Phase 5 (Section 11) — interface, if we do it.

---

## 16. Next step

Confirm **Prerequisites (Section 5)**, then start **Phase 1, Task 1.1**: run `tables_to_excel.py` on 2–3 real PDFs and note what works and what doesn’t. Proceed task by task from there.
