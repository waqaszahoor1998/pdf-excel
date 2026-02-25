# PDF → Excel

Turn PDFs into Excel files. You can pull **all tables** from a PDF (runs offline, no API) or use **Ask AI** to describe what you need (e.g. “taxes for January”) and get only that part as a spreadsheet.

---

## Setup

Use a virtual environment so dependencies stay in the project:

```bash
cd pdf-excel
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Ask AI only:** Copy `.env.example` to `.env` and add a key. **Gemini** is free ([get key](https://aistudio.google.com/app/apikey)) — set `GEMINI_API_KEY`. Or use **Anthropic** (paid) with `ANTHROPIC_API_KEY`. Don’t commit `.env`.

---

## Run

**Web UI (easiest)** — Start the app, then upload a PDF and choose “All tables” or “Ask AI” with a short description. Download the Excel file when it’s done.

```bash
flask --app app run
```

Open http://127.0.0.1:5000 in your browser.

**CLI** — Same idea from the terminal. All tables (offline) or Ask AI (uses your API key).

```bash
python run.py tables report.pdf                    # all tables → one .xlsx
python run.py ask report.pdf "taxes for January"   # Ask AI → Excel with what you asked for
```

Use `-o path/to/output.xlsx` to set the output path. Default is next to the PDF with the same name.

---

## Notes

- **Sample PDF:** Run `python scripts/make_sample_pdf.py` to create `sample_report.pdf`, then try the commands above on it.
- **PDFs:** Digital (text-based) only; no password-protected or scanned PDFs. Ask AI has a 32 MB / 100 page limit.
- **Offline:** “All tables” never sends data out. “Ask AI” sends the PDF to the provider (Gemini or Anthropic) over HTTPS; it’s not used for training.
