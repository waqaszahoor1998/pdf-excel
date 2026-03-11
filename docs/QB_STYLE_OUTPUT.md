# Getting QB-style organized output (like “QB Automation Sheet”)

The target is **well-organized Excel**: one sheet per report type, clear sheet names (Net Assets, Operations, PLSummary, etc.), and **tables with proper column headers in the first row** and data in columns underneath—not labels stacked in column A.

---

## What “QB-style” means

- **Sheet names**: Standard names like **Net Assets**, **Operations**, **Partner Capital**, **PLSummary**, **Journal Entry Import**, **Journal Entries**, **Unrealized**, **Change in Dividend**, **Change in Interest**, **Alt Inv Transfer**, plus **Account Summary**, **Asset Allocation**, **Portfolio Activity**, **Tax Summary**, **Holdings**.
- **Layout**: Each sheet has a section title (optional) and then a **table**: first row = column headers (e.g. Account Name, Market Value, Cash In, Cash Out, PNL, Market Value), following rows = data with the same number of columns.
- **No junk**: No disclaimers, footers, or prose in the table area.

---

## How the app gets there

1. **Section names**  
   Extraction (pdfplumber or VL) produces sections. Each section has a **name** (e.g. “Statement of Net Assets”, “MTD PNL Per Trading Account Summary”). The app maps those to sheet names using:
   - **Built-in patterns** in `tables_to_excel.py` (`REPORT_TITLE_TO_SHEET`): e.g. “statement of net assets” → **Net Assets**, “mtd pnl per trading account summary” → **PLSummary**.
   - **Config** in `config/qb_cleanup.json` → `title_to_sheet`: add `["phrase in title", "Sheet Name"]` for your PDFs.

2. **Table structure**  
   Each section has **headings** (one row of column names) and **rows** (list of rows, same number of columns). The Excel writer puts the headings in the first row and the rows below so you get proper columns, not everything in column A.

3. **QB transform**  
   When you use `run.py tables` or the web “Extract to Excel”, the pipeline runs **transform_extracted_to_qb** on the workbook (formatting, grouping). So the same extraction that fills the sheets also drives the QB-style layout.

---

## VL (scanned PDFs)

For the **vision model** path, the VL prompt asks the model to:

- Use **standard report/section titles** when they match (e.g. “Statement of Net Assets”, “MTD PNL Per Trading Account Summary”, “Portfolio Activity”, “Holdings”).
- Output **one line of column headers** (TAB-separated), then **one row per line** (TAB-separated).

That way the parser can build sections with correct **name** and **headings**/rows, and the app can map the name to a QB-style sheet name and write a proper table.

---

## Adding your own sheet names

In **`config/qb_cleanup.json`**, add entries to **`title_to_sheet`**:

```json
"title_to_sheet": [
  ["statement of holdings", "Holdings"],
  ["your pdf section title or phrase", "Your Sheet Name"]
]
```

The first element is a phrase that can appear in the section/report title (case-insensitive); the second is the exact Excel sheet name you want. This is used in addition to the built-in patterns.

---

## Summary

- **QB-style** = clean sheet names + one table per sheet with **header row** and **data in columns**.
- Section **names** from extraction are mapped to those sheet names via built-in patterns and `config/qb_cleanup.json` → `title_to_sheet`.
- Table structure is preserved when sections have **one row of column headers** and **rows** with the same number of columns (e.g. from VL TAB-separated output or from pdfplumber).
- For VL, the prompt is tuned to ask for standard report titles and TAB-separated headers/rows so the result matches this format.
