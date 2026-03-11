# Plan: Add Qwen2.5-VL for vision-based extraction

This plan adds **Qwen2.5-VL-7B** (vision–language) as an option so we can:
- Handle **scanned PDFs** and image-heavy pages without a separate OCR step (VL “reads” the image).
- Offer an **offline “Ask AI” backend** that sees PDF pages as images (like SmolLM but with vision).

**Model choice:** Qwen2.5-VL-7B-Instruct, GGUF, **Q4_K_M** (~4.7 GB) + **mmproj** (vision encoder).  
**VL** = Vision–Language (model sees images and text together).

---

## What we're building (scope — do not hardcode)

We are building **universal PDF extraction**: extract the major/important data from any PDF, then expose it in a consistent way.

- **Pipeline:** **PDF → JSON → Excel** (and later, other formats from JSON). JSON is the **canonical intermediate**; Excel is the **default export** for now. Future: other outputs (e.g. CSV, other layouts) from the same JSON.
- **Universal:** Support many PDF types (different banks, custodians, audits, reports). No hardcoding for a single document type or layout. Section names, column names, and sheet structure should come from the document and/or config (e.g. `config/qb_cleanup.json`, `config/extract_schema.json`), not from one sample PDF.
- **Example only:** The sample PDF (e.g. Goldman Sachs statement) and sample Excel (e.g. QB Automation Sheet) are **one example** for testing and reference. They are not the product definition. Do not hardcode sheet names, column names, or custodian-specific logic for that sample; keep extraction and mapping generic and config-driven.

**Example document (testing only):** One sample is a broker statement PDF and a “perfect” Excel export from it. Use it only to validate that the pipeline (PDF → JSON → Excel) works on real data; do not encode its layout or names into the code.

---

## Goals

| Goal | Description |
|------|-------------|
| **Scanned PDFs** | Use VL to extract text/tables from image-only or scanned pages (covers ROADMAP Phase 6.1 without classic OCR). |
| **Offline Ask AI with vision** | New backend `--backend qwen2vl`: same “Ask AI” flow but the model sees page images instead of extracted text. |
| **No new OCR dependency** | Rely on VL’s built-in vision instead of Tesseract/pytesseract for the VL path. |

---

## Prerequisites

- [ ] **Hardware:** ~6 GB VRAM or ~8 GB RAM for Q4_K_M + mmproj (or run on CPU if slower is OK).
- [ ] **Software:** Python 3.10+; `llama-cpp-python` with vision support (or another GGUF runner that supports mmproj).
- [ ] **Model files:**  
  - `Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf` (main model, ~4.7 GB)  
  - `mmproj-Qwen2.5-VL-7B-Instruct-f16.gguf` (or the mmproj from the same repo)  
  From: **ggml-org/Qwen2.5-VL-7B-Instruct-GGUF** on Hugging Face.

---

## Phase 1 — Get the model and run it locally

**Goal:** Confirm we can run Qwen2.5-VL-7B (GGUF + mmproj) and get text from an image.

| # | Task | Details |
|---|------|--------|
| 1.1 | Download GGUF + mmproj | Run `python scripts/download_qwen2vl.py` (downloads to `models/qwen2.5-vl-7b/` or `QWEN2VL_MODEL_DIR`). Uses Hugging Face Hub. |
| 1.2 | Install deps | `pip install -r requirements-vl.txt` (llama-cpp-python + huggingface_hub). For GPU see requirements-vl.txt. |
| 1.3 | Run PDF through VL | `python -m extract_vl path/to/file.pdf` — renders pages to images, runs VL on each, prints extracted text. Optional: `--max-pages 5`, `--out output.txt`. |
| 1.4 | Use from code | `from extract_vl import extract_pdf_with_vl; text = extract_pdf_with_vl("file.pdf", max_pages=3)` for integration. |

**Sign-off:** One PDF is fed to the model and we get coherent extracted text.

---

## Phase 2 — Use VL for scanned / image-only PDFs

**Goal:** When a PDF has no (or very little) extractable text, render pages to images and run VL to get text/tables, then feed that into the existing pipeline.

| # | Task | Details |
|---|------|--------|
| 2.1 | Detect “no text” PDFs | In `tables_to_excel.py` (or a helper): after extraction, detect if we got almost no text (e.g. empty or very low character count). Option: flag from `extract_sections_from_pdf` or a separate `needs_vision_fallback(pdf_path)`. |
| 2.2 | PDF → images | Use an existing dependency (e.g. pdf2image, PyMuPDF) to render selected pages to images. Prefer reusing what the project already has (e.g. PyMuPDF in extract_smollm). |
| 2.3 | VL extraction module | New module (e.g. `extract_vl.py`): load Qwen2.5-VL once (or lazy), accept list of images (or PDF path + page indices). Prompt VL **generically**: e.g. “Extract all text and tables from this document page. Preserve structure (sections, headers, rows).” Output: text or structured blocks that map into the **existing canonical JSON/section format** (sections + rows) so the same JSON → Excel path works. No document-type–specific or custodian-specific prompts; keep prompts configurable (e.g. from config or prompts/) if needed. |
| 2.4 | Plumb into extraction | From `tables_to_excel.py` (or the main extraction entry): when “no text” is detected, call the VL extraction module on rendered page images, then convert VL output into the same section/table structure (list of sections with rows) that the rest of the pipeline expects. Reuse existing JSON → Excel path. |
| 2.5 | Config and env | Add config (e.g. in `config/extract.json` or .env): enable/disable VL fallback, path to GGUF and mmproj, optional page limit for VL (to avoid running 100 pages through VL). |

**Sign-off:** One scanned or image-only PDF runs through the pipeline and produces Excel (and JSON) using the VL path when “no text” is detected.

---

## Phase 3 — VL as “Ask AI” backend

**Goal:** New CLI and (optionally) UI option: “Ask AI” using Qwen2.5-VL so the model sees page images instead of extracted text.

| # | Task | Details |
|---|------|--------|
| 3.1 | `extract_qwen2vl.py` | New extractor (similar to `extract_smollm.py`): input = PDF path + query. Render PDF pages to images (or a subset), send images + query to Qwen2.5-VL, parse model output (CSV/table or JSON), then use existing `extract_csv_from_response` / `csv_to_excel` (and multi-table logic if applicable). |
| 3.2 | `run.py ask --backend qwen2vl` | In `run.py`, add `qwen2vl` to the `--backend` choices; when selected, call the new VL-based extractor instead of Anthropic or SmolLM. Pass model path (or env) for GGUF + mmproj. |
| 3.3 | Optional: Web UI | If the app has “Ask AI”, add an option (e.g. dropdown or env) to use the VL backend when running locally. Document that VL is heavier and may be slower. |
| 3.4 | Docs and defaults | README: when to use `--backend qwen2vl` (offline, need vision, have ~6 GB VRAM). Document env vars (e.g. `QWEN2VL_MODEL_PATH`, `QWEN2VL_MMPROJ_PATH`). |

**Sign-off:** `python run.py ask report.pdf "taxes for January" --backend qwen2vl` produces an Excel file using the local VL model.

---

## Phase 4 — Polish and edge cases

| # | Task | Details |
|---|------|--------|
| 4.1 | Page limits and timeouts | For VL path: configurable max pages to send to the model (e.g. first N pages or only pages that failed text extraction). Timeout or skip if a single page takes too long. |
| 4.2 | Hybrid use | Optional: use pdfplumber first; for pages that yield no/very little text, run only those pages through VL and merge results. |
| 4.3 | Tests | At least one test: (1) VL backend is importable and (2) with a small fixture image, VL returns non-empty text (or mock the model and test the parsing path). |

---

## Order of work (summary)

1. **Phase 1** — Get model, install runner, run one image → text (unblock everything else).
2. **Phase 2** — Scanned PDF path: detect no text → render pages → VL → existing pipeline.
3. **Phase 3** — Ask AI backend: `--backend qwen2vl` and optional UI.
4. **Phase 4** — Limits, hybrid logic, tests.

---

## Where this fits in the rest of the project

- **PLAN.md:** Phase 5 (interface) and “Future possibilities” (OCR) — VL implements “vision-based extraction” and covers scanned PDFs without classic OCR.
- **ROADMAP.md:** Phase 6.1 (OCR for scanned PDFs) — VL path **replaces** the need for a separate OCR step for the “no text” case; we can still add Tesseract later as an alternative if desired.
- **Backends:** Today we have `anthropic` and `smollm` for `run.py ask`. After Phase 3 we have **qwen2vl** as a third, offline, vision-capable backend.

---

## Quick reference

| Item | Choice |
|------|--------|
| Model | Qwen2.5-VL-7B-Instruct |
| Format | GGUF Q4_K_M (~4.7 GB) + mmproj |
| Source | ggml-org/Qwen2.5-VL-7B-Instruct-GGUF (Hugging Face) |
| Inference | llama-cpp-python (or other GGUF runner with vision/mmproj) |
| New files | `extract_vl.py` (VL extraction), `extract_qwen2vl.py` (Ask AI backend), optional `scripts/run_qwen2vl_image.py` |
| Config | VL fallback on/off, paths to GGUF/mmproj, page limits |

---

*Last updated: from “let’s make a plan” discussion (Qwen2.5-VL, no separate OCR for VL path).*
