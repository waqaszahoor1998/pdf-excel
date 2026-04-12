# PDF → Excel (v3.2)

Extract **tables and structured data from PDFs** into **Excel** and **JSON**. Supports both **digital PDFs** (text-based) and **scanned/image-only PDFs** (via a local vision model). Output is **QB-style**: clean sheet names, one header row per table, merged continuations, and config-driven mapping so you can share the tool and run it on any system.

---

## What it does (current features)

- **PDF → JSON → Excel**  
  Extract tables from a PDF into a canonical JSON (sections with name, headings, rows), then build an Excel workbook. JSON is the intermediate so you can edit or reuse the data.

- **Digital PDFs (no AI)**  
  Use **pdfplumber** (and PyMuPDF fallback) to extract text and tables. One command: `run.py tables report.pdf` → `output/report.xlsx` and `output/report.json`.

- **Scanned / image-only PDFs**  
  Use the **vision model** (Qwen2.5-VL) to “read” each page as an image and output tables. Pipeline: PDF → images → VL → text → parser → JSON → Excel. Enable via **“Use vision model”** in the web app or `extract_vl ... --json` then `run.py from-json`.

- **QB-style output**  
  - Section names (e.g. “Holdings (Continued)”) are **normalized** and mapped to standard sheet names (Holdings, Cash Activity, Unrealized, PLSummary, etc.).  
  - Sections that map to the **same sheet** are **merged** into one sheet (e.g. all Holdings continuations → one Holdings sheet).  
  - Each table has a **clear header row** and data in columns; no header row is dropped as “prose.”  
  - Config in `config/qb_cleanup.json` lets you add `title_to_sheet` mappings for new PDFs without code changes.

- **Web app**  
  Run locally: upload a PDF, choose “Extract to Excel” (or “Use vision model” for scanned PDFs), get a ZIP with .xlsx and .json. No data sent to the cloud for extraction.

- **CLI**  
  `run.py tables`, `run.py json`, `run.py from-json`, `run.py ask` (optional AI backend). See [Run](#run) below.

---

## What’s in v3.2

**New in v3.2**

- **Hybrid extraction** (`hybrid_extract.py`): library path first; optional VL for difficult pages. See `docs/HYBRID_ROUTING.md`.
- **QB-oriented typed fields**: `field_service.py`, `fields_from_qb_output.py`, `qb_posting_rules.py` for structured JSON alongside QB workbooks.
- **Family template population**: `template_populator.py` (optional account/template workflows).

**Carried from v3.1**

- **Vision (VL) pipeline** for scanned PDFs: Qwen2.5-VL-7B (GGUF), PyMuPDF for page→image, table-focused prompt, TAB-separated parsing into canonical JSON.
- **Web app** option “Use vision model (for scanned PDFs)” so the same UI works for both digital and scanned PDFs.
- **QB-style organization**: normalized “(Continued)” names, merge-by-sheet-name, built-in and config `title_to_sheet` mappings (Holdings, Cash Activity, Unrealized, Dividends and Distributions, Fixed Income, etc.).
- **Clean tables**: single-header-row path so column headers are never altered or dropped; QB transform no longer treats header rows as prose; blank rows removed.
- **Docs**: TEST_AND_SHARE (how to test and share), VL_GPU_WHY_AND_FIX (CUDA/GPU), VL_PIPELINE_AND_LIBRARIES (libraries vs model, prompt), QB_STYLE_OUTPUT (target format and mapping).

---

## Requirements

- **Python 3.10+**
- **For digital PDFs only:** `pip install -r requirements.txt` — no API key, no model.
- **For scanned PDFs (VL):** `pip install -r requirements-vl.txt`, then run `python scripts/download_qwen2vl.py` once (~4–5 GB). Optional but recommended: **NVIDIA GPU + CUDA** for speed (see `docs/VL_GPU_WHY_AND_FIX.md`).
- **For Ask AI (CLI):** set `ANTHROPIC_API_KEY` in `.env`.

---

## Quick start (run on your system)

```bash
# Clone the v3.2 branch, then cd into the repo folder, e.g.:
# git clone -b v3.2 https://github.com/waqaszahoor1998/pdf-excel.git
cd pdf-excel
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1

# macOS/Linux
# source venv/bin/activate

pip install -r requirements.txt
```

### Keep your copy in sync with GitHub

From the project root (with your venv activated):

1. **See what changed:** `git status`
2. **Pull latest on your branch:** `git pull origin v3.2` (replace `v3.2` with your branch if different)
3. **After you edit files:**  
   `git add -A` → `git commit -m "Short description of the change"` → `git push origin v3.2`
4. If `git push` asks for auth, use a [personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) or SSH keys as configured for your GitHub account.

The repo includes **`.flaskenv`** so the web app listens on **port 8003** by default when you run `flask --app app run`.

**Digital PDF → Excel:**

```bash
python run.py tables path/to/report.pdf
# → output/report.xlsx and output/report.json
```

**Web UI:**

```bash
flask --app app run
# Open http://127.0.0.1:8003 → upload PDF → Extract to Excel
# Port 8003 is set in .flaskenv (FLASK_RUN_PORT). Override: --port 9000 or set FLASK_RUN_PORT in .env
```

**Scanned PDF (vision model):**  
See [Scanned PDFs (VL)](#scanned-pdfs-vision-model-vl) below and `docs/TEST_AND_SHARE.md`.

---

## Run

### Web UI

```bash
flask --app app run
```

Open **http://127.0.0.1:8003**. Upload a PDF, then:

- **Extract to Excel** — Uses pdfplumber (digital) or, if you check **“Use vision model”**, the VL pipeline (scanned). You get a ZIP with .xlsx and .json.
- **Ask AI** — Requires `ANTHROPIC_API_KEY` in `.env`; sends the PDF to Anthropic for natural-language extraction.

### CLI

| Command | What it does |
|--------|----------------|
| `python run.py tables report.pdf` | Extract all tables → `output/report.xlsx` and `output/report.json`. |
| `python run.py json report.pdf` | Extract → JSON only. |
| `python run.py from-json output/report.json -o output/report.xlsx` | Convert an existing JSON (e.g. from VL) to Excel. |
| `python run.py ask report.pdf "query"` | Ask AI (needs API key). |

Use `-o path/to/out.xlsx` to set the output path. Default output directory is `output/` (override with `OUTPUT_DIR` in `.env`).

### Scanned PDFs (vision model / VL)

1. Install VL deps and download the model (once):

   ```bash
   pip install -r requirements-vl.txt
   python scripts/download_qwen2vl.py
   ```

2. Extract to JSON (you can limit pages with `--max-pages N`, e.g. first 5 pages), then convert that JSON to Excel:

   ```bash
   # PDF → JSON (e.g. first 5 pages only)
   python -m extract_vl path/to/scanned.pdf --json output/report.json --max-pages 5

   # JSON → Excel
   python run.py from-json output/report.json -o output/report.xlsx
   ```

3. **GPU:** If you use CUDA, set `CUDA_PATH` and add CUDA `bin` to `PATH` before running. See `docs/VL_GPU_WHY_AND_FIX.md`.

Full steps and “how to share with someone else” are in **`docs/TEST_AND_SHARE.md`**.

---

## How it works

- **Digital PDFs:** pdfplumber (and PyMuPDF fallback) extract text and table structure from the PDF. Sections are mapped to sheet names via `config/qb_cleanup.json` and `tables_to_excel.py` patterns; continuations are merged into one sheet per name. Then `transform_extracted_to_qb` adds QB-style formatting.
- **Scanned PDFs:** Each page is rendered to an image (PyMuPDF); the image + a **prompt** are sent to Qwen2.5-VL. The model returns **text** (e.g. TAB-separated headers and rows); our parser turns that into the same canonical JSON. From there, the same JSON → Excel path produces the workbook.
- **Libraries vs model:** PyMuPDF, pdfplumber, and openpyxl are **libraries** (no AI). The **model** is Qwen2.5-VL (GGUF + mmproj), used only for the VL path. See `docs/VL_PIPELINE_AND_LIBRARIES.md`.

---

## Configuration

- **`config/extract.json`** — Extraction limits, prompts, long-PDF options.
- **`config/qb_cleanup.json`** — `footer_phrases`, `header_fragment_merges`, **`title_to_sheet`** (map section titles to sheet names for new PDFs).
- **`.env`** — Copy from `.env.example`. Set `OUTPUT_DIR`, `ANTHROPIC_API_KEY` (for Ask AI), `QWEN2VL_MODEL_DIR` (or explicit paths) for VL.

---

## Documentation

| Doc | Contents |
|-----|----------|
| **`docs/TEST_AND_SHARE.md`** | How to test (digital + VL), how to share the project and run it on another system. |
| **`docs/PDF_JSON_FORMAT.md`** | Why JSON first, shape of `sections`, editing workflow. |
| **`docs/EXPECTED_FORMAT.md`** | QB-style sheet naming and layout targets. |
| **`docs/QB_STYLE_OUTPUT.md`** | Merging sections, `title_to_sheet`, colors. |
| **`docs/HYBRID_ROUTING.md`** | How hybrid extraction routes weak pages to VL (`docs/hybrid.md` overview). |
| **`docs/VL_GPU_WHY_AND_FIX.md`** | Why use GPU, CUDA/DLL issues, and how to fix them (no fallback to CPU). |
| **`docs/VL_PIPELINE_AND_LIBRARIES.md`** | What PyMuPDF, pdfplumber, openpyxl do; how the VL pipeline and prompt work. |
| **`docs/VL_JSON_IMPROVEMENTS.md`** | Notes on improving VL JSON output. |

---

## Running on someone else’s system

1. They need **Python 3.10+** and the project folder (clone or zip).
2. **Digital PDFs only:**  
   `python -m venv venv` → activate venv → `pip install -r requirements.txt` → `python run.py tables file.pdf` or run the web app with `flask --app app run` → open **http://127.0.0.1:8003**.
3. **Scanned PDFs too:**  
   Also install `requirements-vl.txt`, run `scripts/download_qwen2vl.py`, and (optional) set up CUDA. Full steps: **`docs/TEST_AND_SHARE.md`**.

---

## Notes

- **Privacy:** Web app and `run.py tables` / VL path run locally; no PDF data is sent to the cloud for extraction. `run.py ask` uses Anthropic’s API.
- **Sample PDF:** `python scripts/make_sample_pdf.py` creates `sample_report.pdf` for testing.
- **PDF limits:** Web upload 40 MB; VL can be limited with `--max-pages`.
