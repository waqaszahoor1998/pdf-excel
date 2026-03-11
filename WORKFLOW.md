# How the app works (simple version)

---

## Pipeline: PDF → JSON → Excel

The **main idea**: we turn the PDF into **JSON first** (structured data: sections, headings, rows). That JSON is the **canonical intermediate** — it’s easier to check, edit, or reuse. Then we **build the Excel from that JSON**. So it’s not “PDF straight to Excel”; it’s **PDF → JSON → Excel**. That way:

- The same data lives in one clear format (JSON) before anything else.
- You could edit the JSON and re-generate Excel without touching the PDF.
- Other tools can use the same JSON (APIs, scripts).

On the **web**, when you click Extract, the app does: extract PDF → write JSON (in a temp folder) → read that JSON → build Excel from it → send you the Excel. The JSON is not shown or saved for you, but **Excel is produced from JSON**. If you use the **command line** (`run.py tables report.pdf`), you get both the Excel and the JSON file so you can keep or edit the JSON.

---

## Two ways to run the app

### 1. In the browser (web app)

You start the server (`flask --app app run`), open http://127.0.0.1:5000, upload a PDF, and click a button. You get an Excel file back as a download.

### 2. In the terminal (command line)

You type commands like `python run.py tables report.pdf` in a terminal. The program runs and writes Excel (and maybe JSON) files to a folder (e.g. `output/`). No browser, no upload page — just: run command → files appear.

“CLI” = **command-line interface** = this second way (typing commands).

---

## What “offline” means

- **Offline / local extraction** = the PDF never leaves your computer. The program (pdfplumber) reads the PDF on your machine and pulls out tables. No internet, no API key.
- **Ask AI** = the PDF (or parts of it) is sent to Anthropic’s servers. They run the AI and send back extracted data. This needs the internet and an API key.

So: **offline** = “we do the extraction here”; **Ask AI** = “Anthropic does it over the internet”.

---

## What actually runs when

### In the browser

| What you choose        | What happens                                                                 | Result        |
|------------------------|-------------------------------------------------------------------------------|---------------|
| **Extract to Excel**   | PDF is read on your machine → tables extracted → reorganized into sheets   | One .xlsx     |
| **Ask AI** + query    | PDF + your question sent to Anthropic → they return extracted content       | One .xlsx     |

### In the terminal (commands)

| Command                         | What it does                                                                 | Result              |
|---------------------------------|-------------------------------------------------------------------------------|---------------------|
| `python run.py tables report.pdf` | Same kind of extraction as “Extract to Excel”, but **no** extra reorganization | .xlsx + .json       |
| `python run.py json report.pdf`   | Same extraction; **only** the data is written as JSON (no Excel file)         | .json only          |
| `python run.py ask report.pdf "query"` | Sends PDF + query to Anthropic (like Ask AI in the browser)              | One .xlsx           |

So:

- **PDF → Excel** = extract tables from the PDF and put them in an Excel file (and maybe also JSON).
- **PDF → JSON** = same extraction, but the result is saved **only** as a JSON file (sections, headings, rows). Useful if you want to process the data in code or another tool instead of opening Excel.

---

## Short summary

- **Web** = use the site: upload PDF, get Excel (or use Ask AI and get Excel).
- **Terminal / CLI** = use commands: `run.py tables` or `run.py json` or `run.py ask`; you get files in a folder.
- **Offline** = extraction runs on your machine (no internet). **Ask AI** = uses the internet and Anthropic.
- **PDF → Excel** = tables from the PDF written to .xlsx. **PDF → JSON** = same data written to .json. The design is **PDF → JSON → Excel**: JSON is the intermediate; Excel is built from the JSON. To map tables correctly you can do **PDF → JSON first**, edit the JSON if needed, then **JSON → Excel** (web: use the two-step forms; CLI: `run.py json report.pdf` then `run.py from-json report.json -o report.xlsx`).
