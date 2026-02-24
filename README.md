# PDF → Excel

A **PDF-to-Excel converter** (backend code that reads PDFs and writes Excel). Our **end goal** is to have an **AI agent** on top: you say what you need in plain language (e.g. *“give me the company taxes for January 2026”*) and get that data as Excel. We build the converter first so it works reliably; then the AI agent is the layer that decides *what* to extract and uses the same pipeline to produce Excel.

**Today:** You can (1) extract all tables from a PDF to Excel (offline, no AI), or (2) use the AI agent: PDF + your prompt → Excel with only the part you asked for.

### Single entry point: `run.py`

One script for both modes, with **batch** (multiple PDFs) and **progress** messages:

```bash
# Extract all tables (offline)
python run.py tables report.pdf
python run.py tables a.pdf b.pdf              # batch: one Excel per PDF
python run.py tables ./pdfs/                  # all PDFs in directory

# AI agent: extract what you ask for
python run.py ask report.pdf "company taxes for January 2026"
python run.py ask a.pdf b.pdf "sales table"   # same query, multiple PDFs
```

---

## AI agent: extract what you ask for (end goal)

You provide a PDF and a natural-language prompt. The agent (Claude via Anthropic) finds the matching data and you get an Excel file.

**Setup:** See “How we use Anthropic” below (API key in `.env`). Then:

```bash
python extract.py path/to/document.pdf "company taxes for January 2026"
# Creates path/to/document.xlsx with that data
```

See the rest of this README for more examples, confidentiality, and options.

---

## Converter (offline): extract all tables (no AI, no API key)

**Setup once:**

```bash
cd pdf-excel
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Run:**

```bash
python tables_to_excel.py path/to/your.pdf
# Creates path/to/your.xlsx with one sheet per table (e.g. Page1, Page2_T2)
```

Optional output path:

```bash
python tables_to_excel.py report.pdf -o output/report.xlsx
```

Part of the **converter** foundation: uses **pdfplumber**; no API key, no data sent out. Use when you can’t or don’t want to use the AI (e.g. confidentiality). For “give me only this part” use the AI agent above.

---

## How the AI agent works

The flow is:

1. **You provide the PDF** — You give the script the path to your PDF (today: CLI; later we can add upload in a web UI).
2. **You tell the AI what you need in a prompt** — e.g. *"I need the company taxes for January 2026 from this PDF"* or *"Extract the sales table from section 3 and give it to me in Excel."*
3. **The AI agent does the work** — The PDF and your prompt are sent to Claude (Anthropic). Claude reads the PDF, finds the part that matches your request, and returns that data as a table.
4. **You get Excel** — The script turns that table into an `.xlsx` file and saves it (same name as the PDF by default, or use `-o path/to/output.xlsx`).

So: **PDF in → your prompt (what data you need) → AI finds it → Excel out.**

**Example prompts you can use:**

- *"I need the company taxes for January 2026 from this PDF in Excel."*
- *"Extract the sales table from Q3 and give me the result as a table for Excel."*
- *"Get the list of employees from the HR section and put it in Excel."*
- *"I need only the revenue figures for 2025 from this report, in Excel."*

You don’t have to say “in Excel” in the prompt — the agent always returns a table that we save as Excel. Saying it can still help the AI focus on tabular data.

---

## How you use it today vs. future UI

**Right now there is no UI** — only the command line. You run:

```bash
python extract.py path/to/document.pdf "I need the company taxes for January 2026"
```

and the script writes an Excel file. So the “agent” is already implemented in the backend (PDF + your prompt → Claude → Excel); you’re just talking to it via the terminal.

**When we add a UI (Phase 5 in the plan),** we can do it in two main ways. Yes — one of them is **exactly like a chat box with an LLM**: you tell the agent what to do in natural language.

### Option A — Simple form (one shot)

- **Upload** a PDF (or choose a file).
- **One text box:** “What do you need from this PDF?” (e.g. “taxes for January 2026”).
- **Button:** e.g. “Extract to Excel”.
- **Result:** You get a **Download Excel** link. No conversation, just: upload → type what you want → get file.

### Option B — Chat-style (like LLMs)

- You **upload or attach the PDF** once (or the app remembers the last one).
- You see a **chat box** (like ChatGPT / Claude): you type what you want, e.g. *“Get me the company taxes for January 2026 from this PDF and give it to me as Excel.”*
- The **agent replies** in the chat: e.g. a short message + a **preview of the table** (or “Here’s your data”) + a **“Download Excel”** button.
- You can **keep chatting** about the same PDF: e.g. *“Now extract the Q3 sales table”* or *“Give me the employee list from the HR section.”* Each reply can include a new Excel download. So it feels like talking to an LLM and telling it what to do — that’s how the AI agent would work in the UI.

So: **the “agent” is already implemented (CLI).** When we add a UI, it can be either a **simple form** or a **chat-style interface** where you tell it what to do in a chat box, like with LLMs. The plan (Phase 5) leaves the choice open; we can pick the chat UI if that’s the experience you want.

---

## How we use Anthropic (AI agent)

This project uses **Anthropic’s API** (Claude) for the AI extraction. No other AI provider is required.

1. **Get an API key** — [console.anthropic.com](https://console.anthropic.com/) → API keys → Create key.
2. **Set it in the project** — Copy `.env.example` to `.env` and set:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-...
   ```
3. **Run the AI extraction** — Use `extract.py` with your PDF and a natural-language query (see below). The script sends the PDF to Claude and writes the extracted table to Excel.

The key is read from `.env` (never commit `.env`; it’s in `.gitignore`).

---

## AI-powered extraction (Anthropic)

When you want to pull **only** the data you ask for from a long PDF:

1. Ensure `.env` has `ANTHROPIC_API_KEY` (see above).
2. Run:

```bash
python extract.py path/to/document.pdf "company taxes for January 2026"
```

See the rest of this README for more options (custom output path, model choice).

---

## Confidentiality & privacy (important for sensitive data)

Your data may be confidential. Here’s how the two paths compare.

### If you use the AI path (`extract.py`)

- **Not used for training** — Anthropic’s policy: they **do not train** their models on your API content (your PDFs and prompts). Your data is not used to improve Claude. See [Anthropic Commercial Terms](https://www.anthropic.com/legal/commercial-terms) and their [Privacy Center](https://privacy.anthropic.com/).
- **Private, but not offline** — Your PDF and prompt are sent over the internet (HTTPS) to Anthropic’s servers. They process the request and return the table. API data is typically retained for a limited time (e.g. 30 days) then deleted. So it’s private and not used for training, but the content **does leave your machine** while the request is processed.
- **For stricter needs** — Enterprise / custom agreements can include things like zero data retention. Check Anthropic’s current offerings if you need that.

### If data must never leave your machine (fully offline)

- **Use only the non-AI path** — Run **`tables_to_excel.py`** only. It uses **pdfplumber** on your computer; no API calls, no network, no third party. The PDF never leaves your machine. Output is written locally.
- **Trade-off** — You get **all** tables from the PDF in one Excel file. You cannot ask in natural language for “only taxes for January 2026”; for that you’d need the AI path (which sends data to Anthropic).

### Summary

| Path | Data leaves your machine? | Used for training? | Best for |
|------|---------------------------|--------------------|----------|
| **`tables_to_excel.py`** | No (fully offline) | N/A | Confidential PDFs; you’re fine with “all tables” in Excel. |
| **`extract.py` (Anthropic)** | Yes (to Anthropic, over HTTPS) | No | When you need “only this part” and accept sending the PDF to the API. |

So: for **maximum confidentiality and offline use**, use only **`tables_to_excel.py`**. For **AI-powered “give me just this data”** with a strong no-training guarantee, use **`extract.py`** and rely on Anthropic’s policy (data still goes to their servers).

---

## What you need

- **Python 3.10+**
- For AI step: **Anthropic API key** from [console.anthropic.com](https://console.anthropic.com/)

## Version

Current version is in **`VERSION`** (e.g. `1.1.0`). Show it: `python run.py --version`. When you release, bump the number in `VERSION` and tag (e.g. `v1.2.0`). Minor = new features/fixes; major = breaking changes.

## Running tests

After `pip install -r requirements.txt`:

```bash
pytest
```

Or from the project root: `python -m pytest`. Run one file: `pytest tests/test_extract.py`. Tests cover CSV parsing and Excel writing in `extract.py` (no API calls).

## PDF limits and quirks

- **AI path (`extract.py`):** Max **32 MB** per PDF, **100 pages** (Anthropic limit). Larger files are rejected before the API is called.
- **Both paths:** **Password-protected or encrypted PDFs** are not supported; you’ll get a clear error.
- **Both paths:** We target **digital (text-based) PDFs**. Scanned PDFs (image-only) need OCR and are not supported yet.
- **Offline path:** No hard size limit; very large PDFs may be slow or run out of memory.
- **Exit codes:** Scripts exit with **0** on success and **1** on failure (so you can use them in scripts or n8n).
- **Overwrite:** By default the output file is overwritten. Use `--no-overwrite` with `tables_to_excel.py` to fail if the file already exists.

## Output paths

- **Default:** If you don’t pass `-o`, the Excel file is written next to the PDF with the same name and a `.xlsx` extension (e.g. `report.pdf` → `report.xlsx` in the same folder).
- **Custom path:** Use `-o path/to/output.xlsx` to choose the file path. The **parent directory is created automatically** if it doesn’t exist.
- **Overwrite:** Default is to overwrite. Use `--no-overwrite` with `tables_to_excel.py` to avoid overwriting.

## AI usage (extract.py)

**CLI:**

```bash
python extract.py path/to/document.pdf "company taxes for January 2026"
python extract.py report.pdf "sales table from Q3" -o output/sales.xlsx
```

**In code:**

```python
from extract import extract_pdf_to_excel
extract_pdf_to_excel("report.pdf", "taxes for January 2026", "january_taxes.xlsx")
```

**Optional model:**

```bash
python extract.py doc.pdf "your query" --model claude-opus-4-6
```

Default is `claude-sonnet-4-20250514`.

---

## Using with n8n

You can run the PDF→Excel converter (and AI agent) from [n8n](https://n8n.io) workflows in two ways.

### Option 1: Execute Command node (self-hosted n8n only)

If n8n is **self-hosted** and the host (or container) has **Python + this project’s dependencies** installed:

1. In n8n, add an **Execute Command** node.
2. Run the script with arguments from the workflow, for example:
   - **Offline (all tables):**  
     `python /path/to/pdf-excel/tables_to_excel.py /path/to/input.pdf -o /path/to/output.xlsx`
   - **AI agent:**  
     `python /path/to/pdf-excel/extract.py /path/to/input.pdf "{{ $json.query }}" -o /path/to/output.xlsx`
3. Use workflow data for the PDF path and (for AI) the query — e.g. a previous step saves an uploaded PDF to a file and passes the path; the query can come from a form or trigger.
4. The Excel file is written to the path you set with `-o`; a later step can attach it to an email, upload to Drive, etc.

**Note:** Execute Command is **not** available on n8n Cloud (security). It must be enabled on self-hosted n8n (disabled by default in n8n 2.0+). The command runs in the n8n process’s environment, so `ANTHROPIC_API_KEY` must be set there for the AI path.

### Option 2: HTTP API (when we add it)

If we add a **REST API** (e.g. Phase 5 “API” option) that accepts a PDF and optional query and returns Excel:

1. In n8n, use an **HTTP Request** node.
2. Call our API (e.g. `POST /extract` with PDF file + query, or `POST /tables` for offline).
3. Use the response (e.g. Excel file or download URL) in the next steps.

This works with n8n Cloud as long as the API is reachable (e.g. our server or a tunnel). We don’t have this API yet; it’s planned as an optional Phase 5 item (see PLAN.md).
