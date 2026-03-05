# GS Preferred and Hybrid Securities Statement: PDF Structure and JSON Mapping (EXAMPLE ONLY)

This document analyses **one sample** GS statement PDF to illustrate the kinds of content (tables, key-value blocks, text) that a generic canonical JSON schema must support. **Nothing here must be hard-coded in the implementation.** The GS PDF is just a reference; the real schema and extraction logic must work for any PDF (other brokers, JPM, simple reports, etc.) using only generic rules (e.g. “tables have rows/columns”, “key-value pairs”, “text blocks”).

---

## 1. Document overview (this sample only)

- **Pages:** 54
- **Extractor used in practice:** PyMuPDF (pdfplumber gets no text from this PDF)
- **Recurring header/footer:** "GS: PREFD AND HYBRID SECURTIES" (55 times), "Period Ended December 31, 2025", "Portfolio No: XXX-XX366-3"
- **Main sections** (from TOC on page 1): General Information, Overview, US Tax Summary, Holdings, Investment Activity, Cash Activity

---

## 2. Page-by-page content types

| Page range | Section | Content type | Description |
|------------|---------|--------------|-------------|
| 1 | TOC | navigation | Table of contents: section name → page number |
| 2 | General Information | key_value + text | Portfolio number, base currency, mandate name; recipient names/addresses; period |
| 3 | Overview | tables + key_value | Total portfolio value; Portfolio Activity (market value summary); Investment Results table; Performance table (portfolio vs indices) |
| 4–5 | US Tax Summary | tables + text | Reportable Income (Dividends, Interest breakdown); Non-Reportable Items; Realized/Unrealized gains; tax disclaimer paragraph |
| 6–17 | Holdings | table (wide) | Fixed income holdings: security name (multi-line), quantity, market price, market value, accrued income, cost, unrealized gain, yield %, estimated income; ratings line per security |
| 17+ | Investment Activity | tables | Purchases & Sales; Non Purchases & Sales (transaction lines) |
| 18+ | Cash Activity | table | Transactions affecting cash: type, date, description, net amount, end-of-day balance; bank deposit; closing balance |
| Later | Tax / regulatory | tables + text | Qualified US/Foreign dividends, reportable interest, tax information; regulatory/legal text |

---

## 3. Data elements to capture in JSON (generic concepts; this sample’s values are illustrative only)

### 3.1 Document metadata (generic)

- **Generic:** `source_file`, `page_count`, `extractor` (which library was used). Any other key-value pairs (e.g. period, portfolio id, currency) should be **detected generically** from the document, not hard-coded from this PDF. This sample has: period_ended, portfolio_number, base_currency, mandate_name — other PDFs will have different or no such fields.

### 3.2 Table of contents (if present)

- **Generic:** If the first page (or any page) looks like a TOC (short section names + page numbers), emit a generic structure e.g. array of `{ "label": "...", "page": N }`. Section names must not be hard-coded; this sample has "General Information", "Overview", etc. — other PDFs will have different labels or no TOC.

### 3.3 Key-value and text blocks (generic)

- **Generic:** Any page can have key-value pairs (label + value) or text blocks; capture as `type: "key_value"` with `pairs: [[label, value], ...]` or `type: "text"` with `lines: [...]`. Do not hard-code field names — detect structure only.
- Optional: full raw text for “Statement Detail” and footer.

### 3.4 Overview (page 3)

- **Generic:** Any table is `type: "table"` with `name` (from heading if present), `headings`, `rows`. No fixed column names or section names; this sample has "Portfolio Activity", "Investment Results", "Performance" — other PDFs will have different tables.

### 3.5 Nested or multi-block sections (generic)

- **Generic:** A page can have multiple content blocks (tables, key_value, text). Order and block types are derived from layout, not from known section names. This sample has tax-style tables and a disclaimer paragraph — other PDFs will have different content.

### 3.6 Wide tables / multi-line rows (generic)

- One logical **table** (possibly split across pages) with columns:
  - Security name (multi-line: issuer, series, coupon, next call, ratings)
  - Quantity / Current Face
  - Market Price
  - Market Value / Accrued Income
  - Unit Cost
  - Adjusted Cost / Original Cost
  - Unrealized Gain (Loss)
  - Yield to Maturity %
  - Estimated Annual Income
- **Generic:** Represent as one table (rows = list of cell arrays); optionally record page/continuation. Do not hard-code column or field names.
- Optional: record page/continuation so “continued” pages are still in order.

### 3.7 Investment Activity (pages 17+)

- **Generic:** Any table where each row looks like a transaction is still a `type: "table"` with generic `headings` and `rows`. No fixed column set.

### 3.8 More tables and totals (generic)

- **Generic:** Same as above: tables and key-value or text blocks. Normalized structures (e.g. `cash_activity[]` with typed fields) can be **optional** and produced by downstream or by generic heuristics (e.g. “table with date-like column and amount column”), not by hard-coding “Cash Activity” or “Transactions affecting cash”.

### 3.9 Repeating headers/footers

- “GS: PREFD AND HYBRID SECURTIES”, “Period Ended…”, “Portfolio No…” Repeating header/footer text can be detected by frequency and either stored once in metadata or kept in per-page raw_text. No hard-coding of specific strings.

---

## 4. Proposed canonical JSON shape for this PDF type

```json
{
  "metadata": {
    "source_file": "<original filename>",
    "page_count": 54,
    "extractor": "pymupdf"
  },
  "toc": [
    { "label": "<detected section label>", "page": 2 }
  ],
  "pages": [
    {
      "page_number": 1,
      "section_role": "<generic role if detectable, e.g. toc | content | unknown>",
      "content": [ { "type": "table", "name": "<from heading>", "rows": [...] } ]
    },
    {
      "page_number": 2,
      "section_role": "content",
      "content": [
        { "type": "key_value", "name": "<from first line or null>", "pairs": [["<label>", "<value>"], ...] },
        { "type": "text", "name": "<optional>", "lines": ["..."] }
      ]
    },
    {
      "page_number": 3,
      "section_role": "content",
      "content": [
        { "type": "key_value", "name": null, "pairs": [["<label>", "<value>"]] },
        { "type": "table", "name": "<from heading>", "headings": [...], "rows": [...] }
      ]
    },
    {
      "page_number": 4,
      "section_role": "content",
      "content": [
        { "type": "table", "name": "<from heading>", "rows": [...] },
        { "type": "text", "name": null, "lines": ["..."] }
      ]
    }
  ],
  "holdings": null,
  "cash_activity": null,
  "summary": null
}
```

- **pages[]**: Every page is present; `section_role` identifies the high-level section (toc, general_information, overview, tax_summary, holdings, investment_activity, cash_activity, other). Each page’s `content[]` has blocks of type `table`, `key_value`, or `text`.
- **holdings / cash_activity / summary**: If present, must be produced by generic rules or downstream — no broker- or sample-specific field names in the implementation.

---

## 5. Extraction challenges for this PDF

1. **PyMuPDF only:** No text from pdfplumber, so the pipeline must use PyMuPDF (and optionally Camelot/Tabula for table detection; currently they often find “no tables” on this PDF).
2. **Multi-line security names:** Holdings rows span 2–3 lines (issuer, series/coupon, ratings). The extractor must group these into one row per security and attach the numeric row to the correct name.
3. **Key-value vs table:** Blocks like “MARKET VALUE AS OF DECEMBER 01, 2025” + “40,678,757.48” are label-value pairs; they can be stored as `key_value` or as a two-column table.
4. **Repeated footers:** Decide whether to strip “GS: PREFD AND HYBRID SECURTIES” and “Page X of 54” from content or keep them in `raw_text` per page.
5. **Section boundaries:** “FIXED INCOME (Continued)” and “Cash Activity (Continued)” indicate the same logical section across pages; `section_role` and optional `section_continued: true` can capture that.

---

## 6. Recommendation for “perfect” JSON

- **Phase 1 (generic canonical):** Implement the generic schema from the plan: `metadata` + `pages[]` with `content[]` blocks (`type`: table | text | key_value). For the GS PDF, every table and text block is emitted in page order; key_value can be used where we detect label-value pairs.
- **Phase 2 (GS-aware):** Add optional, format-specific top-level keys (`toc`, `holdings`, `cash_activity`, `summary`) populated by a generic rules only (no broker- or sample-specific logic) over the generic `pages[].content`. That gives one JSON that is both page-faithful and easy to consume for Excel/HTML (e.g. “Holdings” sheet from `holdings`, “Cash” from `cash_activity`).

**Implementation principle:** Nothing from this one sample PDF may be hard-coded. Schema and extraction must be generic and work for any PDF.
