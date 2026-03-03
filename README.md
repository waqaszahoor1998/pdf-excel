# PDF → Excel

Turn PDFs into Excel files. The **web app** extracts tables and produces a **QB-format** workbook (Account Summary, Asset Allocation, Portfolio Activity, Tax Summary, etc.) — all **locally**, no API keys. The **CLI** can extract all tables (offline) or use **Ask AI** with a natural-language query (requires an API key).

---

## Requirements

- **Python 3.10+**
- For the web app and `run.py tables`: no API key.
- For `run.py ask`: set `ANTHROPIC_API_KEY` in `.env` (see below).

---

## Setup

Use a virtual environment so dependencies stay in the project:

```bash
cd pdf-excel
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Optional (only for CLI "Ask AI" or running extract scripts):** Copy `.env.example` to `.env` and add your key. For `run.py ask` you need **Anthropic** — set `ANTHROPIC_API_KEY`. Output and extraction behaviour are configurable via `OUTPUT_DIR`, `ANTHROPIC_MODEL`, and the options in `config/extract.json` or the env vars listed in `.env.example`. Don’t commit `.env`.

---

## Run

### Web UI (recommended)

Start the app, then open the URL and upload a PDF. The default is **Extract to QB format**: tables and sections are turned into clean Excel sheets (Account Summary, Asset Allocation, PLSummary-style, etc.). Or use **Ask AI** with a natural-language query (requires `ANTHROPIC_API_KEY`).

```bash
flask --app app run
```

Open **http://127.0.0.1:5000** in your browser.

Alternatively: `python app.py` (runs with debug on port 5000).

### CLI

- **All tables (QB format)** — One run extracts every table and writes **both** an Excel file and a JSON file (same base name: `report.xlsx` and `report.json`). No mode choice: one stream.

  ```bash
  python run.py tables report.pdf
  ```
  Output: `output/report.xlsx` and `output/report.json`. See **PDF_AND_JSON.md** for the JSON shape (row/column mapping, verification with `row_count`/`column_count`).

- **JSON only** — If you want only the JSON file (e.g. for scripting):

  ```bash
  python run.py json report.pdf
  ```

- **Ask AI** — Describe what you want (e.g. “taxes for January”) and get only that as Excel. Uses your `ANTHROPIC_API_KEY` in `.env`:

  ```bash
  python run.py ask report.pdf "taxes for January"
  ```

Use `-o path/to/output.xlsx` to set the output path. If you don’t use `-o`, output is written to the **default output directory** (by default `output/`), with the same base name as the PDF and `.xlsx`. With multiple PDFs, each gets its own file in that directory. You can override the default directory by setting `OUTPUT_DIR` in `.env` (e.g. `OUTPUT_DIR=exports`).

---

## Configuration

Behaviour is **config-driven** (no hardcoded limits or prompts in code):

- **`config/extract.json`** — Extraction limits, single vs multi-table mode, prompt paths, optional structured output and long-PDF options. Environment variables override file values (e.g. `EXTRACTION_MODE`, `QUERY_MAX_LENGTH`).
- **`prompts/`** — System prompts: `extraction_single.txt` (one table), `extraction_all.txt` (multiple CSV blocks → multiple sheets). Optional `structure.txt` for the long-PDF “summarize then extract” step when `long_pdf_enabled` is true.
- **`.env`** — API key, `ANTHROPIC_MODEL`, `OUTPUT_DIR`, and any override for the keys in `config/extract.json`.

See `.env.example` and `config/extract.json` for all options.

---

## Notes

- **Sample PDF:** Run `python scripts/make_sample_pdf.py` to create `sample_report.pdf`, then try the web app or CLI on it.
- **PDFs:** Text-based (digital) only; no password-protected or scanned/image-only PDFs. Web upload limit is 40 MB; the Ask AI command has a 32 MB / 100 page limit per provider.
- **Privacy:** The web app and `run.py tables` never send data out. `run.py ask` sends the PDF to Anthropic over HTTPS; it is not used for training.
