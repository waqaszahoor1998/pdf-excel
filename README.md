# PDF → Excel

Extract tables from PDFs to Excel: **all tables** (offline) or **Ask AI** (describe what you want).

## Setup

```bash
cd pdf-excel
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

For **Ask AI**, copy `.env.example` to `.env` and set `GEMINI_API_KEY` (free at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)) or `ANTHROPIC_API_KEY`.

## Run

**Web UI:** `flask --app app run` → open http://127.0.0.1:5000

**CLI:**
```bash
python run.py tables report.pdf                    # all tables
python run.py ask report.pdf "taxes for January"  # Ask AI
```

Sample: `python scripts/make_sample_pdf.py` then run on `sample_report.pdf`. Digital PDFs only; AI path max 32 MB.
