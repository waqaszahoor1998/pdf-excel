# Universal Extraction: Any PDF → JSON

Your prompts and pipeline were tuned on a few PDFs (e.g. Goldman Sachs broker statements). This doc explains **how the same code works for any PDF** when you launch as a product. **Document type is auto-detected from the PDF; the user does not select it.**

---

## 1. Automatic document-type detection (no user selection)

When you run extraction **without** passing a schema type, the system **auto-detects** the document type from the PDF text (first 1–2 pages):

- **Tax-style:** Phrases like "US Tax Summary", "Reportable Income", "Dividends and Distributions", "Form 1099" → use **tax_statement** prompt.
- **Broker-style:** Phrases like "Portfolio Information", "Portfolio Activity", "Statement of Net Assets", "Holdings", "Investment Results" → use **broker_statement** prompt.
- **Neither / other:** Use **universal** prompt (any document type).

Detection is keyword-based on extracted text (PyMuPDF). No extra model call. The chosen type is written to the JSON as **`meta.detected_document_type`** so you can show it in the UI (e.g. "Detected: broker statement").

**Workflow:** User uploads PDF → your app calls `pdf_to_json_vl(pdf_path, json_path)` with **no** `schema_type` → detection runs → the right prompt is used → JSON is written with `meta.detected_document_type` set. No dropdown, no user choice.

---

## 2. One output format for all PDFs

No matter what PDF the user uploads, we always produce the **same JSON schema**:

- **`sections`**: list of `{ "name", "headings", "rows", "row_count", "column_count", "page" }`
- **`meta`**: `pdf_name`, `pages_processed`, timing, and when auto-detected: **`detected_document_type`** (`"broker_statement"`, `"tax_statement"`, or `"universal"`).

So the rest of your product (Excel export, APIs, UI) works the same. What changes by document type is **which prompt we use** and **how accurate** the extraction is—not the shape of the JSON.

---

## 3. Universal prompt (fallback when type is unknown)

We added a **`universal`** prompt profile that **does not assume** any document type or section names:

- It says: “Extract every data table. The document can be any type (invoice, report, statement, form, etc.).”
- For each table: first line = title **as it appears** (or “Table 1” if none), second line = headers (TAB-separated), then data rows (TAB-separated). Include all rows and columns.
- No list of “Portfolio Activity” or “US Tax Summary”; the model uses whatever titles and structure the page actually has.

**How to use it:**

- **CLI:**  
  `python -m extract_vl file.pdf --json out.json --schema-type universal`  
  Or omit `--schema-type` and the default is taken from config (see below).
- **Config:** In `config/vl.json`, set  
  `"schema_type_default": "universal"`  
  so that when your app doesn’t pass a schema type (e.g. user didn’t choose one), extraction uses the universal prompt. That’s the right default for “any PDF” in a product.

So: **for any upload, we can always run with the universal prompt and get a consistent JSON.** Quality will vary by PDF complexity, but the format is stable.

---

## 4. Overriding detection (optional)

If the user tells you the document type, or you detect it, use a **specific** profile so the model can follow a stricter format:

| User uploads / you detect     | Use `--schema-type` (or pass same to `pdf_to_json_vl`) |
|------------------------------|--------------------------------------------------------|
| Unknown / “any document”      | `universal` (default)                                  |
| Broker / investment statement| `broker_statement`                                    |
| Tax summary / tax document    | `tax_statement`                                       |
| Legacy / old behavior        | `generic`                                             |

So:

- **Universal environment:** Default = `universal` in config; same code path for every PDF.
- **Better accuracy when possible:** If the user selects “Broker statement” or “Tax document” in the UI, call the extractor with `schema_type="broker_statement"` or `"tax_statement"`.

---

## 5. Optional: let the user say what to extract

For a “focus on this” flow (like `run.py ask`), you can:

- Let the user type a short instruction, e.g. “only the summary table” or “all tables on page 2”.
- Build a **custom prompt** that includes that instruction and the usual format rules (title line, header line, TAB-separated rows), then call the VL extractor with `prompt=custom_prompt` (and still write the same JSON schema from the parser).

That way one product supports both “extract everything” (universal) and “extract what I care about” (user-driven prompt).

---

## 5. Optional: detect document type from the first page

To avoid asking the user every time:

- Run the VL (or a small classifier) on the **first page only** with a short prompt: “What type of document is this? One of: broker_statement, tax_statement, invoice, report, form, other.”
- Map the answer to a schema type (e.g. `broker_statement`, `tax_statement`) or keep `universal` for “other”.
- Then run the full extraction with that schema type (or universal). You can do this in the background so the user still gets “one button” extraction.

---

## 6. Quality and “review recommended”

- **Same code, different PDFs:** Universal prompt + same parser + same JSON schema = works for any PDF. Accuracy depends on layout and how well the model follows the format.
- **Confidence / review:** You can flag extractions that look odd (e.g. very few sections, empty sections, or repetitive content) and set `meta.requires_review = true` or `meta.validation_warnings = ["..."]` so the UI can say “Review recommended” and still return valid JSON.

---

## 7. Summary for product use

| Goal | What to do |
|------|------------|
| Support **any** PDF with one code path | Use **`schema_type="universal"`** (or omit and set `schema_type_default: "universal"` in `config/vl.json`). Same JSON for all. |
| Better accuracy when type is known | When user selects “Broker statement” or “Tax document”, use **`broker_statement`** or **`tax_statement`**. |
| Optional: user-driven focus | Build a prompt that includes the user’s instruction + format rules; pass it as `prompt=...`; keep writing the same sections/headings/rows JSON. |
| Optional: auto document type | First page → “what type?” → choose schema type (or universal) → run full extraction. |

The prompts you had (broker, tax) are tuned for **those** PDFs. For millions of different PDFs, **default to the universal prompt** so every upload gets a consistent, reasonable extraction; then improve accuracy when you know the type or when the user tells you what to extract.
