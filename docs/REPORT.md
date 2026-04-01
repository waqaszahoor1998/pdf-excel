# Report: PDF extraction pipeline (current status)

## How it runs
### Input
- A PDF file

### Outputs
- **Canonical extraction JSON**: extracted tables/sections with rows/columns and basic metadata for auditability.
- **Excel (optional)**:
  - Excel generated from the JSON (raw extracted tables in spreadsheet form)
  - a standardized/organized workbook (grouped into common sheet types)
- **Typed fields JSON (optional)**: a list of extracted key values (numbers/dates where possible) with confidence and provenance (where each value came from).

## Implemented and verified
### 1) PDF → JSON (canonical extraction)
- Command: `python run.py json <pdf> -o <output.json>`
- Result: structured JSON is produced reliably.
- Improvements added:
  - reduced obvious long narrative/disclosure rows in output tables
  - merged split words/numbers where extraction produced fragments
  - added metadata in JSON for auditability

### 2) JSON → Excel
- Command: `python run.py from-json <output.json> -o <output.xlsx>`
- Result: Excel can be generated directly from the extraction JSON.

### 3) PDF → QB-style workbook (+ JSON)
- Command: `python run.py tables <pdf> -o <output.xlsx>`
- Result: produces:
  - an organized workbook (grouped sheets)
  - a JSON file with the extracted structured data
- Fix included:
  - corrected a case where a “TOC” was incorrectly detected on some PDFs, which previously collapsed output into a single “Other” sheet.

### 4) Typed fields JSON (key values)
- Command: `python run.py fields <pdf> -o <fields.json>`
- Result: produces a list of extracted facts such as:
  - statement period start/end (when detectable)
  - account identifiers (when detectable)
  - key totals and PLSummary-style numbers (when available)
- Each field includes:
  - value (typed where possible)
  - confidence level
  - provenance (where it was read from: sheet/row/column)

## How to run (commands)
- **Extract to JSON**: `python run.py json <pdf> -o output\\extraction.json`
- **Excel from JSON**: `python run.py from-json output\\extraction.json -o output\\from_json.xlsx`
- **Organized workbook (and JSON)**: `python run.py tables <pdf> -o output\\qb.xlsx`
- **Typed fields JSON**: `python run.py fields <pdf> -o output\\fields.json`

## Libraries and model modes
### Default (fast) extraction (offline)
- Uses local PDF table/text extraction libraries (non-AI) for digital PDFs.

### Hybrid / vision model mode (offline, optional)
- For scanned pages or pages that extract poorly, there is a hybrid mode that:
  - runs non-AI extraction first
  - routes only the “bad pages” to a local vision-language model
- This mode is slower, so it is intended only when required.

## Hybrid routing (how “bad pages” are detected)
Pages are routed to the vision model when the non-AI extraction quality is low, for example:
- no table-like structure is detected on the page, or
- the page quality score falls below a threshold, or
- the output shows strong signals of poor extraction (very sparse rows, fragmented section names, or mostly prose).

## How correctness and confidentiality are handled (offline)
### Data confidentiality (offline)
- In the offline modes, the PDF is processed **locally** and is **not sent to any cloud service**.
- Outputs are written only as local files (JSON/Excel) in the project’s output folder.
- If cloud AI is ever used temporarily (separate “Ask AI” mode), sensitive identifiers can be **redacted/replaced** (client names, broker/bank names, account numbers) before sending any content, to preserve confidentiality.

### Correctness (unattended behavior)
- The pipeline uses a **layered approach**: non-AI extraction first, and (only when needed) an optional fallback that processes difficult pages and merges results.
- The pipeline runs **validation checks** on extracted structures. When issues are detected, the output is clearly flagged as **Requires Review** rather than silently producing misleading results.
- The typed fields output (`fields.json`) includes **provenance** (where each value came from) and a **confidence** level, so results are auditable and easier to verify.

## Demonstration artifacts (examples)
Example outputs produced during testing are stored under the `output\\` folder, such as:
- extraction JSON (`*_extraction.json`)
- typed fields JSON (`*_fields.json`)
- Excel generated from JSON (`*_from_json.xlsx`)
- organized workbook (`*_qb.xlsx`)

