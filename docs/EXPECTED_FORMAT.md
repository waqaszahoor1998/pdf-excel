# Source PDF and Target Excel Format

This doc describes the **target Excel structure** the extractor aims for: one sheet per report/section, clear headers, numeric data. The layout is driven by the *content* of the PDF (statements, summaries, etc.), not by a single proprietary format. Names like “QB” in the codebase refer to an early sample file; the product is a general **PDF data extractor** for tabular (and other) content.

## How to use

1. **Web app**  
   Run `flask --app app run` (or `python app.py`), open http://127.0.0.1:8003, upload your PDF.  
   - **Raw extraction**: one sheet per section (good for checking what was extracted).  
   - **Structured workbook**: merged sheets by type and by account (e.g. Period Summary, Asset Allocation, Portfolio Activity, Tax Summary, per-account sheets, Broker Info). Use this for downstream workflows, reporting, or APIs.

2. **Command line (raw)**  
   `python -m tables_to_excel "9004-20251231-Combined-Statement-001.pdf" -o raw.xlsx`

3. **Command line (structured workbook)**  
   `python -c "from pdf_to_qb import pdf_to_qb_excel; pdf_to_qb_excel('your.pdf', 'output.xlsx')"`

---

## Source: Combined broker/custodian statements

The **input** PDFs are combined statements from brokers/custodians, for example:

- **9004-20251231-Combined-Statement-001.pdf** (J.P. Morgan consolidated statement, 46 pages)

Typical structure of these PDFs:

- **Cover / Account Summary** – period (e.g. 12/1/25 to 12/31/25), account numbers (e.g. E79271004, G41269004), Beginning/Ending Market Value, Change.
- **Consolidated Summary** – Asset Allocation (Equity, Cash & Fixed Income), Portfolio Activity (Beginning Market Value, Net Contributions/Withdrawals, Income & Distributions, Change in Investment Value, Ending Market Value, Accruals), Tax Summary.
- **Per-account sections** – Same layout repeated per account (e.g. ABC TRUST ACCT. E79271004, ABC TR ACCT. G41269004): Account Summary, Asset Allocation, Portfolio Activity, Cash & Fixed Income Summary/Detail, Holdings, Tax Summary, Interest on USD Cash, etc.

Section titles you will see in the PDF include: *Account Summary*, *Consolidated Summary*, *Asset Allocation*, *Portfolio Activity*, *Tax Summary*, *Cash & Fixed Income Summary*, *Cash & Fixed Income Detail*, *Equity Summary*, *Equity Detail*.

---

## Target: Structured workbook (sheet-per-section)

The **desired output** is a workbook with one sheet per logical report/section, clear column headers, and numeric/date values (not text where possible). The structure follows the PDF’s sections (e.g. Account Summary, Asset Allocation, Portfolio Activity); an early reference was a sample file named “QB Automation Sheet” — the extractor is not tied to that file, it aims for a clean, consistent layout for any statement/summary-style PDF.

## Overall structure

- **One sheet per report/section** (e.g. Net Assets, Operations, Partner Capital, PLSummary, Journal Entry Import, Journal Entries, Unrealized, Change in Dividend, Change in Interest, Alt Inv Transfer).
- **Header block** at top of each sheet (when present in PDF):
  - Firm: name, address, phone, website
  - Accounting Calendar, Accounting Period, Reporting Currency
- **Entity name** (e.g. AB REVOCABLE TRUST).
- **Report title** (e.g. "STATEMENT OF NET ASSETS | As of 12/31/2025", "STATEMENT OF OPERATIONS | Reporting Period: ...", "MTD PNL Per Trading Account Summary").
- **Data table** with clear column headers and numeric/date values (not text).

## Sheet types and column patterns

| Sheet / report type        | Typical columns / structure |
|----------------------------|-----------------------------|
| **Net Assets**             | Description \| Balance |
| **Operations**              | Financial Account \| month/period columns (dates), YTD |
| **Partner Capital**         | Description \| EK1-L LLC, EK2-L LLC, … \| Total |
| **PLSummary** (consolidated)| Repeated blocks: Account Name \| Market Value \| Cash In \| Cash Out \| PNL \| Market Value (BOM / MTD / EOM) |
| **PLSummary** (per broker)  | Same columns; optional account ID (e.g. 902-7, 808-5); optional notes/references |
| **Journal Entry Import**    | *JournalNo \| *JournalDate \| *AccountName \| *Debits \| *Credits \| Description \| Reference \| Currency \| Location \| Class |
| **Journal Entries**         | Date \| Transaction Type \| Num \| Name \| Memo/Description \| Account \| Debit \| Credit |
| **Unrealized**              | Report title then broker/section; table with description and amounts |
| **Change in Dividend/Interest** | Report title; broker (e.g. GOLDMAN SACHS); table of changes |
| **Alt Inv Transfer**        | Account IDs as headers; row labels (PE, OAI, etc.); Nov / Dec (or period) columns |

## Conventions

- **Numbers** should be numeric in Excel (not text) so formulas work.
- **Dates** should be date type where applicable (e.g. BOM/EOM, JournalDate).
- **Empty cells** for missing values; no need to fill with "N/A" or zero unless that matches the source.
- **Sheet names**: short, no invalid characters; max 31 chars (e.g. "Net Assets", "Operations ", "Partner Capital", "PLSummary", "Journal Entry Import", "Journal Entries", "Unrealized", "Change in Dividend", "Change in Interest", "Alt Inv Transfer").

## Mapping: PDF sections → target sheets

| PDF section (e.g. JPM combined statement) | Target sheet / usage |
|-------------------------------------------|----------------------|
| Account Summary                           | Account Summary or PLSummary-style |
| Consolidated Summary                      | Consolidated Summary / PLSummary |
| Asset Allocation                          | Asset Allocation |
| Portfolio Activity                        | Portfolio Activity / Operations-style |
| Tax Summary                               | Tax Summary |
| Cash & Fixed Income Summary / Detail      | Cash & Fixed Income |
| Equity Summary / Detail                   | Equity (or part of same sheet) |
| Statement of Net Assets (fund accounting) | Net Assets |
| Statement of Operations                   | Operations |
| MTD PNL Per Trading Account Summary       | PLSummary |
| Journal Entry Import / Journal Entries    | Journal Entry Import, Journal Entries |
| Unrealized / Change in Dividend/Interest  | Unrealized, Change in Dividend, Change in Interest |

## Color usage (from sample workbook scan)

| Color        | Hex     | Where used in sample |
|-------------|---------|----------------------|
| **Light green** | 92D050 | Section separator row; first row of each block; **cells that contain account IDs** (e.g. 902-7, 1004, 9511, E79271004) – labels for each side-by-side block. |
| **Yellow**      | FFFF00 | **Formula cells** (e.g. `=SUM(...)`); and the "Checks" label cell. |
| **Orange**      | FFC000 | Occasional emphasis (e.g. Net Assets rows 21–22). Applied in our output to **Totals rows** (first cell = Total / Totals / Total Value). |
| **Light blue**  | D9E1F2 | **Column header row** (Account Name, Market Value, BOM, EOM, etc.) when detected. |

The extractor applies these rules when building the structured workbook: green for section/block and account-ID cells, yellow for formulas and "Checks", orange for Totals rows, blue for header rows.

---

## How extraction can align

1. **Detect report type** from PDF text (broker sections: "Account Summary", "Consolidated Summary", "Asset Allocation", "Portfolio Activity", "Tax Summary"; fund-accounting: "Statement of Net Assets", "MTD PNL", "Journal Entry", etc.) and use for **sheet names**.
2. **Keep header block** (firm, calendar, period, currency) and entity/report title at top of each sheet before the table.
3. **Preserve table structure**: first column = description/account name; following columns = amounts/dates; identify header row and keep it as first data row.
4. **One sheet per logical report** (not necessarily one sheet per PDF page) when the PDF has clear section titles.
