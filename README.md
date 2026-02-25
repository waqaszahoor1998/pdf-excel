# PDF → Excel

Extract tables from PDFs into Excel. Two ways: **all tables** (offline, no API) or **Ask AI** (describe what you want; uses Gemini or Anthropic).

---

## Quick start

**1. Setup** (use a venv so dependencies stay in the project):

```bash
cd pdf-excel
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**2. For Ask AI only:** Copy `.env.example` to `.env` and add your key (see [API keys](#api-keys) below).

**3. Run**

- **Web UI (easiest):** `flask --app app run` → open http://127.0.0.1:5000 → upload PDF, choose “All tables” or “Ask AI” + query, download Excel.
- **CLI:**
  ```bash
  python run.py tables report.pdf                    # all tables (offline)
  python run.py ask report.pdf "taxes for January"  # Ask AI
  ```

Sample PDF: `python scripts/make_sample_pdf.py` then run on `sample_report.pdf`.

---

## API keys (Ask AI)

Use **one** of these. Put it in `.env` (never commit `.env`).

| Provider | Key in `.env` | Cost |
|----------|----------------|------|
| **Gemini** | `GEMINI_API_KEY` | Free — [get key](https://aistudio.google.com/app/apikey) |
| **Anthropic** | `ANTHROPIC_API_KEY` | Paid — [get key](https://console.anthropic.com/) |

Web UI uses Gemini if that key is set, otherwise Anthropic. CLI uses the same.

---

## Options & limits

- **Output path:** `-o path/to/output.xlsx` (CLI). Default: same folder as the PDF, same name with `.xlsx`.
- **PDF limits:** Digital (text) PDFs only; no password-protected or scanned. AI path: max 32 MB, 100 pages.
- **Tests:** `pytest`
- **Version:** `python run.py --version` (see `VERSION` file).

---

## Privacy

- **All tables** (`run.py tables` / `tables_to_excel.py`): Fully offline. PDF never leaves your machine.
- **Ask AI**: PDF and query are sent to the provider (Gemini or Anthropic) over HTTPS. Not used for training; typically short retention. For fully offline use, use only the “all tables” path.

---

## Using with n8n

**Self-hosted n8n:** Use an Execute Command node to run `python tables_to_excel.py ...` or `python extract.py ...` (set `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` in the n8n environment).  
**n8n Cloud:** Would need a REST API (not included yet).
