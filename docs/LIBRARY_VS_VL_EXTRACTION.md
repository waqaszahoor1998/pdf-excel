# Library (pdfplumber) vs VL extraction — why one PDF worked and others “mess up”

This doc explains why the **non-model** extraction (pdfplumber + PyMuPDF/Camelot/Tabula) worked on your sample PDF but failed on others, and what we can do so that the earlier library-based approach is still useful.

---

## Where the library path lives

- **Entry points**: `run.py tables`, `run.py json` → `pdf_to_qb_excel` / `pdf_to_json` → `tables_to_excel.extract_sections_from_pdf()`
- **Code**: `tables_to_excel.py` — `extract_sections_from_pdf()`, `_page_sections_with_headings()`, PyMuPDF/Camelot/Tabula helpers

So the “earlier versions of JSON we extracted without the model” come from this path. The VL path is `extract_vl.py` → `pdf_to_json_vl()` (vision model per page, then same JSON schema).

---

## Why it works on one PDF and messes up on another

The library path uses **fixed heuristics** that match one layout well but not others.

### 1. Single table-detection strategy

- pdfplumber is called with one setting:  
  `TABLE_SETTINGS = {"vertical_strategy": "text", "horizontal_strategy": "text"}`
- **“text”** works when tables have no grid lines and structure is implied by text alignment/whitespace (e.g. many bank statements).
- PDFs with **visible grid lines** often need `"lines"` or `"explicit"` so the library uses line intersections to find cells.
- Result: on a different PDF, table boundaries can be wrong (one big blob, or tables split in the wrong place).

### 2. Fixed section-title patterns

- `_split_table_by_section_titles()` only treats these as section boundaries:  
  **Asset Allocation**, **Portfolio Activity**, **Tax Summary**, **Account Summary** (`SECTION_TITLE_PATTERNS`).
- Other titles (e.g. “US Tax Summary”, “Performance”, “Reportable Interest”, “Non-Reportable Items”) are **not** section boundaries, so either:
  - everything stays in one table, or
  - sections are grouped wrong.

So the pipeline is effectively tuned to a document that uses exactly those four section names and a “text”-friendly layout.

### 3. Fixed spacing tolerances

- **HEADING_GAP_PT = 35**: text within 35 pt above a table is treated as that table’s heading.
- **SECTION_GAP_PT = 18**: when there are no grid tables, a vertical gap &gt; 18 pt starts a new section.
- PyMuPDF fallback uses **ROW_TOLERANCE = 5**, **COL_GAP = 15** and rules like “section title = first cell 10–45 chars, all caps, no numbers in rest of row”.

Different PDFs use different spacing and font sizes. Slightly larger gaps or different line heights cause headings to be missed or wrong text to be attached.

### 4. Extractor selection by score only

- The code runs pdfplumber (and PyMuPDF if needed), then optionally Camelot and Tabula, and picks the **highest-scoring** result (row count + table-like sections − inconsistency penalty).
- On a different PDF, a different extractor may “win” but still produce wrong structure (e.g. wrong number of columns, merged cells). So “best score” does not mean “correct for this layout”.

---

## What we can do

Below are concrete options so the **earlier library-based JSON** and pipeline stay useful instead of being abandoned when the PDF changes.

### Option A — Make the library path more universal (same code, more PDFs)

- **Multiple table strategies per page**  
  Try both `vertical_strategy: "text"` and `vertical_strategy: "lines"` (and optionally `"explicit"`), then either:
  - score each result and pick the best, or
  - merge (e.g. take the result with more consistent column counts or more sections).
- **Configurable / expanded section patterns**  
  Extend `SECTION_TITLE_PATTERNS` (or load from config) to include broker/tax section names: e.g. **US Tax Summary**, **Performance**, **Reportable Interest**, **Non-Reportable Items**, **Investment Results**, **General Information**, **Overview**. Then different statements still split into the right blocks.
- **Layout-adaptive tolerances**  
  Infer typical line height and vertical gap from the first page (e.g. from pdfplumber’s line positions), then derive HEADING_GAP_PT / SECTION_GAP_PT / ROW_TOLERANCE from that instead of fixed pt values.
- **Document-type “profiles”**  
  Add a small config (e.g. “broker_statement”) that defines: table strategy, section patterns, tolerances. When we detect document type (e.g. from first-page text like “Preferred and Hybrid Securities” or “US Tax Summary”), we load that profile. So we support one **type** of PDF, not one single file.

Effect: the same library path can produce good JSON for **more** PDFs of the same kind without switching to the model.

### Option B — Use library only when it’s a good fit (detector + VL fallback)

- **Cheap layout / type check**  
  Before choosing extractor: run pdfplumber on the first page (e.g. `extract_tables()` with both "text" and "lines"), or check for known keywords (e.g. “US Tax Summary”, “Reportable Interest”). If the PDF looks “structured” and similar to the sample we tuned for, use the library path; otherwise use VL.
- **Confidence score after library extraction**  
  After library extraction, compute a simple confidence (e.g. number of sections, column-count consistency, presence of expected section names). If below a threshold, re-run that PDF (or only failed pages) with VL and use that result instead.

Effect: we **reuse** the earlier library JSON when the PDF is “friendly”; we avoid mess when it’s not.

### Option C — Hybrid per page (optional)

- Run library extraction first (fast). For each page:
  - If we get no tables or very few rows, or structure looks broken (e.g. one giant table, or column count varies wildly), run VL **only for that page** and merge into the same JSON.
- So we use the model only where the library fails, and keep library output elsewhere.

### Option D — Use “good” earlier JSON as a template (same document type)

- Keep the JSON you extracted **without the model** from the PDF that worked well.
- Use it as a **schema/template** for the same document type: expected section names, column counts, maybe column headers.
- When processing a **new** PDF of the same type with the library path:
  - Validate or normalize the new extraction against that template (e.g. rename sections to match, pad columns, or flag mismatches).
- We are not reusing the old JSON as **data**, but as a **contract** for what “good” extraction looks like for that type. That can drive Option A (expand section patterns to match the template) or Option B (confidence = similarity to template).

---

## Recommended order

1. **Short term**: Expand **section patterns** (Option A) to include US Tax Summary, Performance, Reportable Interest, Non-Reportable Items, Overview, etc., so the library path at least splits sections correctly for more broker/tax statements. Optionally try **two table strategies** (text + lines) and pick or merge by score.
2. **Next**: Add a **document-type hint or detector** (Option B) so we can choose “library” vs “VL” per PDF, or add a **confidence** step and fall back to VL when library output looks weak.
3. **Optional**: Add a **config profile** (e.g. `config/library_extraction.json`) with table settings and section patterns per doc type, and optionally use **earlier good JSON** as a template (Option D) for validation or normalization.

That way the earlier library-based extraction stays useful: either by making it robust enough for more PDFs of the same type, or by using it only when appropriate and falling back to the model when not.
