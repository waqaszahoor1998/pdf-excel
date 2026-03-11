# VL pipeline, libraries, and how the prompt works

This doc answers: what each library does (vs the model), how PDF becomes JSON, and what “text optional” and the prompt mean.

In **v2.3** extraction was fully manual: pdfplumber (and sometimes PyMuPDF) extracted text/tables from the PDF, and openpyxl wrote Excel. There was **no AI model**. Here we **add** the VL path: for scanned or low-text PDFs we use **Qwen2.5-VL**; we still use **PyMuPDF** to turn pages into images for the model, and the same **JSON → Excel** path (openpyxl via `tables_to_excel`) for the final spreadsheet.

---

## Libraries vs the model

**None of these are the AI model.** They are normal Python libraries:

| Library | Role |
|--------|------|
| **PyMuPDF** (`pymupdf`, import as `fitz`) | Reads PDFs. In the **VL pipeline** we use it to **render each page as an image** (PNG). The vision model cannot read PDF bytes; it needs images. So: PDF → PyMuPDF → page images. Elsewhere (e.g. `tables_to_excel`) it’s also used as a fallback to get text/layout when pdfplumber gets nothing. |
| **pdfplumber** | Reads PDFs and extracts **text and table structure** when the PDF has **embedded/selectable text** (digital PDFs). Used in the main pipeline: `run.py tables`, `run.py json`, and inside `tables_to_excel`. No AI; pure geometry and text extraction. |
| **openpyxl** | Writes **Excel** (`.xlsx`) files. When we have JSON (sections with `name`, `headings`, `rows`), we use openpyxl to build the workbook. So: **JSON → openpyxl → Excel**. |

**The model** is **Qwen2.5-VL** (the GGUF + mmproj you download). It’s a vision–language model: it takes **images + text** and **outputs text**. We use it only when we go through the VL path (e.g. `extract_vl.py`).

---

## VL pipeline: PDF → images → model → text → JSON → Excel

Step by step:

1. **PDF → images**  
   PyMuPDF opens the PDF and renders each page to a PNG (we use it only for that in VL; we don’t send PDF bytes to the model).

2. **Image + prompt → model**  
   For each page image we send to Qwen2.5-VL:
   - the **image** (as a data URI), and  
   - a **text prompt** that tells the model what to do and how to format the answer.

3. **Model → text**  
   The model “looks” at the image and **generates text**. It does not output JSON by itself; it outputs **plain text**. We ask it (via the prompt) to use a format we can parse (e.g. TAB-separated headers and rows).

4. **Text → our code → JSON**  
   Our code parses that text:
   - finds TAB- or pipe-separated lines,
   - detects section names, headers, and data rows,
   - builds the **canonical JSON** structure: `sections` with `name`, `headings`, `rows` (and row/column counts).  
   So the **JSON is produced by our parser**, not directly by the model.

5. **JSON → Excel**  
   Same as the rest of the project: `run.py from-json` (or the app) loads that JSON and uses **openpyxl** (via `tables_to_excel`) to write the `.xlsx` with one sheet per section, headers in the first row, then data rows.

So:

- **“PDF changes to images, then images are sent to Qwen2.5-VL, (then) text (then) optional JSON”** means:  
  We always get **text** from the model. We then **optionally** run our parser and write **JSON** (e.g. when you use `--json report.json`). So “optional” is about whether we **also** produce and save the structured JSON file, not whether we produce text.

---

## Is there a prompt? How does it work?

**Yes. A prompt is sent with every page image.**

The prompt is a short instruction in natural language. For table extraction we use a **table-only prompt** that tells the model to:

- Extract **only** data tables (no disclaimers, headers, footers).
- For each table:
  - First line: table/section name (e.g. "Holdings", "Portfolio Activity").
  - Second line: column headers separated by **TAB**.
  - Next lines: one row per line, cells separated by **TAB**, numbers as numbers.

So we’re not “just giving the PDF”; we’re giving **image + instructions**. The model then types out text in that format; our code parses that text into sections with proper columns and rows so that:

- The JSON has structured tables (name, headings, rows).
- Empty or extra cells are handled by the parser (e.g. padding rows to header length, skipping junk lines).

If the model sometimes outputs markdown or HTML, we strip that and still try to detect TAB- or pipe-separated lines so we can still get tables when possible.

---

## Summary

- **PyMuPDF**: used here to turn PDF pages into **images** for the VL model; elsewhere also for text/layout.  
- **pdfplumber**: used for **text/table extraction** from digital PDFs (no VL).  
- **openpyxl**: used to write **Excel** from our JSON.  
- **VL pipeline**: PDF → (PyMuPDF) → images → (image + **prompt**) → Qwen2.5-VL → **text** → our **parser** → **JSON** → (openpyxl) → Excel.  
- **“Text optional JSON”**: we always get text from the model; “optional” means we can also **parse and save JSON** (e.g. `--json`).  
- The **prompt** is what makes the model output in a parseable form (e.g. TAB-separated tables) so we can build organized, structured data with proper columns and rows in JSON and Excel.
