# PDF → Structured Data Extraction Service (Progress Report)

**Date:** 2026-03-31  
**Project:** `pdf-excel-3.1`  

## Executive summary
We have built a working extraction service that takes a **PDF as the only input** and produces **structured, readable data (JSON)** as the main output. From that same JSON, we can also produce **Excel files** as one downstream format. The core extraction is designed to run **unattended** (no manual steps) and to clearly flag when the document needs review.

In plain terms: **PDF in → structured data out (JSON) → optional Excel out**.

## What the system does (in simple terms)
### 1) Extracts the content into structured JSON (the “engine”)
- The extractor reads the PDF and finds tables/sections.
- It outputs a **canonical JSON file** containing:
  - the extracted **sections**
  - the rows/columns of each table
  - basic audit metadata (PDF name, page count, timestamp)

This JSON is the “main product” because it can later feed:
- Excel
- accounting tools (e.g., QuickBooks workflows)
- databases / reporting pipelines

### 2) Produces Excel as a separate consumer (not the engine)
Excel output is treated as a **separate downstream format** built from the JSON (or from the extracted workbook). This keeps the extractor reusable for future outputs.

### 3) Produces a “typed fields” JSON layer (service-friendly facts)
In addition to the raw extracted tables, we now also produce a second JSON output called **typed fields**.  
This output is a list of useful “facts” with:
- the value (as a number/date where possible)
- a confidence level (high/medium/low)
- where it came from (provenance: which sheet/row/column)

This is the foundation for reliable automation because it is easier to validate than raw tables.

## How it runs (high level)
### Inputs
- **Only required input:** a PDF file

### Outputs
Depending on the command, the system produces:
- **Canonical extraction JSON** (structured tables/sections)
- **Typed fields JSON** (key facts with provenance)
- **Excel** (raw extracted tables or “QB-style” organized workbook)

### Typical run (example)
For a PDF like `9004-20251231-Combined Statement-001.pdf`, a typical run produces:
- `...extraction.json` (structured sections/tables)
- `...fields.json` (typed facts)
- `...from_json.xlsx` (Excel built from JSON)
- `...qb.xlsx` (organized workbook for downstream use)

## Technology used (high level, non-technical)
### Non-AI extraction (default, fast)
Most PDFs that contain real text/tables can be processed quickly using standard PDF table-reading libraries.  
This is the current default path and is what we used for the demo PDF.

### Optional “vision model” extraction (fallback for hard/scanned pages)
Some PDFs contain scanned pages or tables that are hard to read using normal methods.  
For those cases, we built an optional fallback that uses a **vision-language model** (a model that “looks at” page images). The system is designed to:
- run the **non-AI extractor first**
- automatically detect “bad pages”
- use the vision model only on those pages

This improves accuracy on difficult PDFs, but it is slower and heavier, so it is used only when needed.

## Reliability / unattended operation
To support unattended use:
- The pipeline includes **validation checks** that detect inconsistent table shapes.
- When issues are found, the output is clearly marked as **Requires Review** instead of silently pretending it is perfect.
- We added cleanup steps to reduce obvious noise, broken words, and fragmented numbers in the JSON/Excel.

## What we achieved so far (concrete progress)
### A) Working end-to-end pipeline
- PDF → **canonical JSON**
- JSON → **Excel**
- PDF → **organized workbook** (QB-style)
- PDF → **typed fields JSON** (facts + provenance)

### B) Major quality improvements
- Reduced “garbage” rows and long narrative blocks in output tables.
- Merged fragmented text and numeric values (e.g., “Year-En” + “d” → “Year-End”).
- Added audit metadata to outputs (PDF name, page count, timestamp).
- Fixed a routing issue where some PDFs were incorrectly treated as having a TOC, which previously collapsed outputs into a single “Other” sheet.

### C) Demonstration artifacts (ready-to-share outputs)
We generated recording-friendly outputs (JSON/Excel/fields) under the `output/` folder using the provided PDF.

## Current limitations / next priorities
- “Universal extraction” (perfect on any PDF) is a long-term goal; PDFs vary widely.
- The vision fallback is available but can be slow; we will keep it as an “only when needed” layer.
- Next priorities are:
  - stronger validation gates for typed fields
  - document-type routing (so “useful fields” adapt to different PDF classes)
  - broader benchmarking across multiple, different PDF samples

## Bottom line
The core extraction service is working: it reliably converts PDFs into structured JSON (the main output) and can generate Excel and typed fields as downstream products. We have also put in place the foundation for “unattended reliability” via validation, audit metadata, and an optional vision fallback for difficult pages.

