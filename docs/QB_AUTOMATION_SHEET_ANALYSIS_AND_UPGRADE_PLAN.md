# QB Automation Sheet – Full Analysis and Upgrade Plan

This document analyzes **QB Automation Sheet- December 2025.xlsx** (every page/sheet and heading), compares it with the **GS broker statement PDF** (first 5 pages) we extract via VL, and outlines a **phased upgrade plan** so our pipeline can move toward that target structure.

---

## Part 0: Design principles (non-negotiable)

1. **Nothing hard-coded**  
   Section names, heading lists, table layouts, and mapping rules must come from **config or from the document** (e.g. detected headings). No fixed lists that assume one PDF type. New behaviour = config-driven or model/document-driven.

2. **Table fidelity and accuracy**  
   - Preserve **structure**: rows, columns, and their **headings** exactly as in the source. Some headings are **bold**, some normal — preserve that in JSON and Excel.  
   - **Blanks stay blank**: cells that are empty in the source must be empty in JSON and Excel; do not fill from other rows or columns.  
   - Tables are **irregular**: different row counts, different column counts, headers in different rows, “jargon” layouts. The pipeline must support irregular tables, not assume uniform grids.  
   Accuracy and structural fidelity (including bold and blanks) are top priorities.

3. **Performance (future focus)**  
   GPU: RTX 3080 Ti. Per-page time varies a lot (e.g. 4–7 s on some pages, 40–70 s on others). This variance and the long tail are a problem to address as we go (e.g. batch size, quantization, or page-level optimizations).

---

## Part 1: QB Automation Sheet – Structure (Every Sheet)

The workbook is a **multi-entity, multi-broker accounting package** produced for fund/trust accounting (e.g. Akram Fund Services). It is **not** a raw extraction from one PDF; it is a **consolidated, normalized workbook** with specific sheet names and layouts.

### Sheet list (14 sheets)

| # | Sheet name | Max rows | Max cols | Purpose (from content) |
|---|------------|----------|----------|------------------------|
| 1 | **Net Assets** | 73 | 16 | Statement of Net Assets: entity (AB REVOCABLE TRUST), Description + Balance; Assets (Cash, Investment in Securities, Accrued Interest and dividend), Total Assets, Liabilities, Total Net Assets. |
| 2 | **Operations** | 35 | 52 | Statement of Operations: reporting period; Financial Account row with **monthly date columns** (Jan–Nov 2023); Revenues (Interest Income, Dividend Income), Expenses (Broker Fees, etc.), Net Investment Income, Realized/Unrealized Gain, Net Income. |
| 3 | **Partner Capital** | 44 | 12 | Change in Partners' Capital: entity; Description + columns per partner (EK1-L LLC, EK2-L LLC, EK3-L LLC, KCM, Total); Members' Capital, contributions, withdrawals, Net Profit, PPI allocation, Net income after PPI, Members' capital end of year. |
| 4 | **PLSummary** | 45 | 38 | **MTD PNL Per Trading Account Summary**: side-by-side **Consolidated** vs **Goldman Consolidated** (and possibly more). Each block: BOM, MTD (Market Value, Cash In, Cash Out, PNL), EOM; Account Name + values; then Accrued Dividend/Interest, Account/Broker fees, Change in unrealized gain/loss, Dividend/Interest Income, Realized gain/loss, etc.; then Balance Sheet section (Accrued Interest and dividend, Cash, Investment in Securities, Total Asset, Securities sold short, Opening Capital, Capital Contribution/Withdrawal, Retained Earning, Net Income, Total Liabilities, Difference). |
| 5 | **PLSummary AB GS** | 66 | 103 | Same MTD PNL layout but **AB Revocable Trust** with **Goldman Consolidated** vs **Goldman PREFERRED AND HYBRID SECURITIES** (and other sub-accounts). Multiple column blocks per broker/strategy. |
| 6 | **PLSummary Goldman Sachs** | 66 | 81 | Same MTD PNL layout: **Administrative ABC Trust**, **Goldman Sachs Consolidated** vs **Goldman Sachs TRUST: MUNI FI (USHRT DUR)** (and others). Contains **Long term realized gain/loss** (e.g. 14875.57) and **Short term realized gain/loss** (1572.9)—values that can come from GS statement. |
| 7 | **PLSummary J.P. Morgan Chase** | 50 | 73 | Same MTD PNL layout for **ABC Trust**, J.P. Morgan Chase Consolidated vs account **E79271004**. |
| 8 | **PLSummary Wells Fargo** | 50 | 73 | Same MTD PNL layout for **AB Revocable Trust**, Wells Fargo vs account **7087-2855**. |
| 9 | **Journal Entry Import** | 132 | 10 | **QuickBooks-style journal import**: columns *JournalNo, *JournalDate, *AccountName, *Debits, *Credits, Description, Reference, Currency, Location, Class. Rows are journal lines (e.g. Interest Income + offsetting account, Debits/Credits). Multiple journals (e.g. 2025-Dec-9511, 2025-Dec-1004) with balanced debits/credits. |
| 10 | **Journal Entries** | 214 | 9 | Human-readable **Journal**: Date, Transaction Type, Num, Name, Memo/Description, Account, Debit, Credit. One row per line; multi-line entries grouped by journal number. |
| 11 | **Unrealized** | 222 | 42 | **Unrealized Gains and Losses**: entity (AB REVOCABLE TRUST); by broker (e.g. Goldman Sachs); then by account (9027, 8085, 7061, 3091) with **month-end date columns**; rows Cost, Market Value, Unrealized, Change in Unrealized. |
| 12 | **Change in Dividend** | 148 | 40 | **Changes in Accrued Dividend**: entity; by broker (GOLDMAN SACHS); by account (9027, 8085, 7061, 387-9, 200-3) with month-end date columns; Accrued Dividend, Change in Accrued Dividend. |
| 13 | **Change in Interest** | 168 | 40 | **Changes in Accrued Interest**: same structure as Change in Dividend; Accrued Interest, Change in Accrued Interest by month. |
| 14 | **Alt Inv Transfer** | 14 | 5 | **Alt Inv Transfer**: period columns (Nov, Dec); account/entity labels (200-3, 377-0); PE, OAI and numeric transfers. |
| 15 | **PLSummary Wells Fargo Extra** | 46 | 27 | Extra Wells Fargo MTD PNL block (Wells Fargo-2855) with same account-name structure; some rows empty. |

### Recurring structural patterns in QB Automation Sheet

- **Header block**: Often rows 1–10 contain entity name, subtitle, accounting period, currency (e.g. Akram Fund Services, Accounting Calendar/Period, Reporting Currency USD).
- **Section title row**: Bold or standalone row (e.g. "STATEMENT OF NET ASSETS", "MTD PNL Per Trading Account Summary", "Unrealized Gains and Losses").
- **Column headers**: Second or third row with meaningful headers (Description, Balance; or BOM, MTD, MTD, MTD, EOM; or monthly dates).
- **Hierarchy**: Entity → Broker → Account/Strategy → Line items (Account Name + values).
- **Multi-block layout**: Same sheet can have **two or more side-by-side blocks** (e.g. Consolidated vs Goldman; or multiple accounts) with a blank column separator.
- **Numeric columns**: Dates as column headers (month-end); or BOM/MTD Cash In, Cash Out, PNL, EOM; or Debits/Credits. Values are numeric (no currency symbols in cells; optional $ in first column).
- **Formulas**: Some cells are formulas (e.g. Chk, Difference, #DIV/0!, #VALUE!) for reconciliation.

---

## Part 2: GS PDF (First 5 Pages) – What It Contains

- **Page 1**: Cover / TOC (GS PREFD AND HYBRID SECURITIES; General Information, **Overview**, US Tax Summary, Holdings, etc.).
- **Page 2**: **General Information** – Portfolio Information (Portfolio Number, Base Currency, Mandate Name); Duplicate copies sent to (names/addresses).
- **Page 3**: **Overview** – Portfolio Activity (5 rows: Market Value dates, Interest Received, Dividends Received, Change in Market Value, Ending Market Value); Investment Results (Current Month / Current Year × 4 columns: Beginning MV, Net Deposits, Investment Results, Ending MV); Performance (summary row + table with Current Month %, YTD %, Inception to Date % for strategy and benchmarks).
- **Page 4**: **US Tax Summary** – Reportable Income: Dividends and Distributions (Qualified US, Non-Qualified US, Qualified Foreign, Non-Qualified Foreign, Total); Reportable Interest (Corporate Interest, Non-US Interest, Bank Interest, Total Reportable Interest, Total Reportable Income); **Non-Reportable Items** (Accrued Interest Paid at Purchase, etc.).
- **Page 5**: **US Tax Summary (Continued)** – Realized Capital Gains (Long Term Realized Gain (Loss), Total Realized Capital Gains) with Current Month, Quarter to Date, Year to date; Unrealized Gain (Loss) (Current Unrealized Gain (Loss)).

So the **PDF** is a **single broker (Goldman), single strategy (Preferred and Hybrid Securities), single period** statement. The **QB Automation Sheet** is a **multi-entity, multi-broker, multi-account** workbook with time series and journal format.

---

## Part 3: Comparison – PDF Content vs QB Sheets

| PDF section (page) | QB Automation Sheet target | How it fits |
|--------------------|----------------------------|-------------|
| **General Information** (2) | Not a dedicated sheet; could feed **metadata** or **Portfolio Information** in a PLSummary block. | Portfolio Number, Base Currency, Mandate Name could populate headers or a small info block. |
| **Overview – Portfolio Activity** (3) | **PLSummary** / **PLSummary Goldman Sachs** – “Account Name” + Market Value, Cash In/Out, PNL, EOM. | Our row “Market Value as of Dec 1”, “Interest Received”, “Dividends Received”, “Change in Market Value”, “Ending Market Value” map to **one column block** (e.g. BOM/EOM and MTD flows). Not a direct 1:1; needs mapping (e.g. Interest Received → Interest Income row in PNL). |
| **Overview – Investment Results** (3) | Same PLSummary: Beginning MV, Net Deposits, Investment Results, Ending MV = one row (Current Month) or two (Current Month + Current Year). | Fits as **one or two data rows** in the MTD PNL layout (or as a separate mini-table in the same sheet). |
| **Overview – Performance** (3) | Not a standard QB sheet; could be **optional “Performance” sheet** or folded into PLSummary as a footnote block. | Percent returns (Current Month %, YTD %, Inception %) are not in current QB sheet set; could add. |
| **US Tax Summary – Dividends and Distributions** (4) | **Reportable Income** / tax detail; also feeds **Journal Entry Import** (Dividend Income, account mapping). | Row labels (Qualified US, Non-Qualified US, etc.) + Current Month, Quarter to Date, Year to date → can populate a “Dividends and Distributions” table or journal lines. |
| **US Tax Summary – Reportable Interest** (4) | Same: Reportable Interest table; **Journal Entry Import** (Interest Income, etc.). | Corporate Interest, Non-US Interest, Bank Interest, Totals → same 3 time columns. |
| **US Tax Summary – Non-Reportable Items** (4) | Optional section or part of tax detail; **Accrued Interest Paid at Purchase** can feed **Change in Interest** or journal. | Interest Paid on Other Securities, Totals. |
| **US Tax Summary (Continued) – Realized / Unrealized** (5) | **Unrealized** sheet (unrealized gain/loss); **PLSummary** (Long term / Short term realized gain/loss rows); **Journal Entry Import** (realized gain/loss accounts). | Long Term Realized Gain (Loss), Total Realized Capital Gains, Current Unrealized Gain (Loss) with 3 columns each → map to Unrealized sheet and to PNL “Long term realized gain/loss” / “Short term realized gain/loss” / “Change in unrealized gain/loss”. |

**Summary**: The PDF is **one slice** (one broker, one strategy, one period) of what the QB workbook consolidates. To “match” QB Automation Sheet we need: (1) **correct extraction** of every table (Overview + full US Tax Summary + Non-Reportable), (2) **mapping** of those tables into QB **sheet names and column layouts**, and (3) **aggregation** of multiple PDFs/periods and **journal generation** for Journal Entry Import.

---

## Part 4: Gaps Between Our Current Output and QB Automation Sheet

### 4.1 Extraction gaps (VL / parser)

- **Overview missing** when model fails on early pages (decode/memory): we never get Portfolio Activity, Investment Results, Performance.
- **Investment Results** sometimes output as 2 columns (Current Month, Year to Date) instead of 4 columns × 2 rows (Current Month, Current Year).
- **Performance** merged into one 7-column table instead of two tables (summary + percentage).
- **Reportable Interest**: wrong or extra rows (e.g. Qualified Foreign Dividends mixed in); Non-US Interest Current Month wrong (0 instead of 21,465.00).
- **Non-Reportable Items** table missing.
- **US Tax Summary (Continued)**: Long Term Realized Gain (Loss) empty; Total Realized Capital Gains missing Year to date column; blank cells filled from next row (e.g. Municipal Bond).
- **General Information**: we don’t structure Portfolio Number, Base Currency, Mandate Name as a dedicated block (we could add a “Portfolio Information” section).

### 4.2 Schema / workbook structure gaps

- **Sheet names**: We use section-based or page-based names (e.g. “Portfolio Activity”, “Reportable Income”, “US Tax Summary”). QB uses **fixed names**: Net Assets, Operations, Partner Capital, PLSummary, PLSummary AB GS, PLSummary Goldman Sachs, Journal Entry Import, Journal Entries, Unrealized, Change in Dividend, Change in Interest, Alt Inv Transfer.
- **Layout**: We write “one section = one or more tables” (title, then header row, then data). QB uses **multi-block** layouts (Consolidated | Goldman | …), **time columns** (month-end dates), and **hierarchy** (entity → broker → account).
- **Account naming**: QB uses a chart-of-accounts style (e.g. “Interest Income”, “INVESTMENTS - OTHER:INVESTMENTS AT GOLD…”). We output **literal PDF labels** (e.g. “Corporate Interest”, “Non-US Interest”).
- **Journal Entry Import**: We do not produce *JournalNo, *JournalDate, *AccountName, *Debits, *Credits. That requires **rules** to map PDF line items to accounts and to generate balanced debits/credits.
- **Multi-PDF / multi-period**: QB has many columns (months, accounts). We process **one PDF at a time**; no consolidation or time-series stacking.

### 4.3 Data quality gaps

- **Blanks**: Model sometimes fills blank cells (e.g. Municipal Bond row) from the next row; we added prompt + post-process to reduce this.
- **Numeric format**: QB uses raw numbers (no commas in some places); we keep commas from PDF. Minor.
- **Three-column consistency**: Current Month, Quarter to Date, Year to date must all be present where the PDF has them; we added prompt for that.

---

## Part 5: Upgrade Plan (Phased)

### Phase 1: Extraction quality (current focus)

- **1.1** Keep improving VL prompts and post-processing so that for **any** broker/tax PDF we get:
  - Overview (Portfolio Activity, Investment Results, Performance summary + Performance %) when present.
  - Investment Results as 4 columns × 2 rows (Current Month, Current Year).
  - Reportable Interest with only the five correct rows; Non-US Interest and all cells exact.
  - Non-Reportable Items as a separate table when present.
  - US Tax Summary (Continued) with all three columns for Realized/Unrealized; no copying from next row.
- **1.2** Add optional **General Information** / **Portfolio Information** section (Portfolio Number, Base Currency, Mandate Name) from page 2 when detected.
- **1.3** Re-run and regression-check on GS PDF (and optionally other broker/tax PDFs) so that statement_12+ matches PDF structure and values.

**Deliverable**: One-PDF JSON/Excel that is **accurate and complete** for that PDF’s pages (no missing Overview, no wrong/mixed rows, no missing columns).

---

### Phase 2: Map extracted sections to QB sheet names and layout

- **2.1** Extend **config** (e.g. `config/qb_cleanup.json` or new `config/qb_sheet_mapping.json`) to define:
  - Which **section names** (or page numbers) map to which **QB sheet name** (e.g. “Portfolio Activity” + “Investment Results” + “Performance” → “Overview” or “PLSummary Goldman Sachs”).
  - For **PLSummary-style** sheets: which PDF rows map to which “Account Name” in the QB template (e.g. Interest Received → Interest Income, Dividends Received → Dividend Income, Change in Market Value → Change in unrealized gain/loss).
- **2.2** Add a **layout mode** in `tables_to_excel` or `pdf_to_qb`: “by QB sheet” instead of “by section name”. When enabled, merge sections into the right sheet(s) and write blocks in QB order (e.g. BOM, MTD columns, EOM).
- **2.3** Support **page_to_sheet** in JSON meta or config so that “page 3” → “Overview”, “page 4” and “page 5” → “US Tax Summary” (or “Reportable Income” + “US Tax Summary (Continued)”). Already partially there; ensure all our sections have correct `page` and that mapping covers every target sheet we need.

**Deliverable**: One-PDF Excel that has **QB-style sheet names** and **grouped content** (e.g. one Overview sheet with Portfolio Activity + Investment Results + Performance), and US Tax Summary on one sheet with Dividends, Reportable Interest, Non-Reportable, Realized/Unrealized.

---

### Phase 3: PLSummary block structure (MTD PNL)

- **3.1** Define a **PLSummary template**: column headers (BOM, Market Value, Cash In, Cash Out, PNL, EOM; then Balance Sheet section with Accrued Interest, Cash, Investment in Securities, etc.).
- **3.2** **Mapping table**: PDF “Portfolio Activity” / “Investment Results” / “Performance” rows → PLSummary “Account Name” and which column (BOM vs EOM vs MTD). Example: “Market Value as of Dec 1” → BOM Market Value; “Ending Market Value” → EOM Market Value; “Interest Received” → Interest Income (MTD); “Change in Market Value” → Change in unrealized gain/loss.
- **3.3** Implement a **writer** that, given extracted sections from one GS statement, fills one **block** of a PLSummary sheet (one strategy, one period). Optionally support **two blocks** on one sheet (e.g. Consolidated vs Preferred and Hybrid) if we have two PDFs or two sections.

**Deliverable**: For a single GS statement PDF, generate an Excel sheet “PLSummary Goldman Sachs” (or “Overview”) with one block that has the correct Account Name rows and BOM/MTD/EOM columns populated from the PDF.

---

### Phase 4: Multi-PDF and time columns

- **4.1** Support **multiple PDFs** as input (e.g. one PDF per broker or per month). Design: either (a) run VL per PDF, merge JSONs with a “source” tag (broker, period), or (b) run VL once per PDF and then a separate “consolidation” step that merges section lists.
- **4.2** Add **time dimension**: when multiple periods are present, create **date columns** (e.g. Dec 2025, Nov 2025) and put values in the right column. This implies section metadata or config: “this section is for period YYYY-MM”.
- **4.3** Optional: **Net Assets** and **Operations** sheets from **aggregated** data (e.g. from multiple broker statements + manual or other inputs). Lower priority until Phases 1–3 are solid.

**Deliverable**: Ability to run pipeline on 2+ PDFs and produce one workbook with multiple blocks or multiple time columns where applicable.

---

### Phase 5: Journal Entry Import and Journal Entries

- **5.1** **Account mapping config**: PDF line item (e.g. “Interest Income”, “Dividend Income”, “Long term realized gain/loss”) → QB account string (e.g. “Interest Income”, “INVESTMENTS - OTHER:INVESTMENTS AT GOLD…”). May be broker-specific.
- **5.2** **Journal rules**: For each PDF section (e.g. Reportable Interest, Dividends and Distributions), define which lines create **debit** vs **credit** and to which account. Example: Interest Income 1964.53 → Credit Interest Income, Debit INVESTMENTS - OTHER:….
- **5.3** **Generate Journal Entry Import** rows: *JournalNo, *JournalDate, *AccountName, *Debits, *Credits, Description, Reference. Ensure each journal balances (sum Debits = sum Credits).
- **5.4** **Journal Entries** sheet: same data in human-readable form (Date, Transaction Type, Num, Name, Memo, Account, Debit, Credit).

**Deliverable**: From one (or more) broker statement PDFs, optional **Journal Entry Import** and **Journal Entries** sheets populated from Reportable Income, Dividends, Realized/Unrealized, etc., with configurable account mapping.

---

### Phase 6: Unrealized, Change in Dividend, Change in Interest

- **6.1** These sheets are **time-series by account** (month-end columns). Our PDF has **one period** (e.g. Dec 2025). So for a single PDF we could fill **one column** (e.g. Dec 31, 2025) for the relevant account.
- **6.2** Map “Accrued Interest and dividend” and “Change in …” from PDF to “Accrued Interest” / “Change in Accrued Interest” (and similarly for dividend) in the QB layout. Requires account id (e.g. portfolio number) and period in metadata.
- **6.3** Unrealized sheet: “Current Unrealized Gain (Loss)” from US Tax Summary (Continued) → one cell in Unrealized for that account/period. Cost/Market Value may come from Holdings or other pages we don’t extract yet.

**Deliverable**: When we have one period and one strategy, at least **one column** of Unrealized / Change in Dividend / Change in Interest populated from the PDF; multi-period as in Phase 4.

---

## Part 5b: Universal PDF vs QB-specific (Phases 2 & 3)

**Problem**: The QB sheet names and PLSummary layout are based on **one** target (the manually made Excel for your GS PDF). Other PDFs have different section names (e.g. "Account Summary", "Tax Information") and different table layouts. If we hardcode QB names and PLSummary for all PDFs, we break the universal pipeline.

**Design: optional, config-driven QB mode.**

| Mode | When | What happens |
|------|------|----------------|
| **Universal (default)** | No QB config, or user does not enable QB output. | Phase 1 only. Sheet names = **extracted section names** (or page-based). No renaming, no PLSummary. Any PDF gets accurate extraction with whatever names the PDF has. |
| **QB mode** | User enables QB output and selects a **mapping profile** (e.g. "goldman_broker_statement"), or we auto-detect document type and pick a profile. | Phase 1 → Phase 2: **config** maps *source* section names (or patterns) to *target* QB sheet names. **Unmapped sections** keep their extracted name or go to a sheet like "Other". So a Fidelity PDF might map "Account Summary" → "Overview" and "Tax Information" → "US Tax Summary" under a `fidelity_statement` profile; unknown sections stay as-is. Phase 3 (PLSummary) runs only if the **selected profile** defines a PLSummary row/column mapping for that doc type. |
| **New / unknown PDF** | No matching profile (or user chooses "universal"). | Output is universal: no QB sheet names, no PLSummary. User can later add a new profile in config so that next time this PDF type gets QB treatment. |

**Config shape (conceptual)**  
- **Profiles** per document type or broker: `goldman_statement`, `fidelity_statement`, `generic_broker`, etc.  
- Each profile: `section_name_patterns` → QB sheet name (e.g. `"Portfolio Activity" | "Investment Results"` → `"Overview"`); optional `plsummary_row_map` for Phase 3.  
- **Unmapped** sections are never dropped: they either keep the extracted name or go to "Other", so every PDF still gets all its content.

So: **Phase 1 is always universal**. Phases 2 and 3 are **optional transforms** applied only when a QB profile is selected; different PDFs can use different profiles or no profile.

---

## Part 5c: Heading-based extraction (universal backbone)

**Idea**: In the PDF, **headings** are the main section titles (e.g. "Overview", "US Tax Summary", "General Information"). Under each heading there are **tables and data**. Some headings span multiple pages (e.g. "US Tax Summary" on page 4 and "US Tax Summary (Continued)" on page 5). If we **detect headings** and **attach every table to its heading**, we get a structure that is both universal and aligns with how the QB sheet is organized (one sheet per major heading, with that heading’s content inside).

**Why this helps**

- **Universal**: We don’t assume specific names. We detect whatever headings the document has (e.g. bold title line, standalone section title). Any PDF has some notion of “heading” and “content under it.”
- **Continued handling**: When we see "US Tax Summary (Continued)" we treat it as the **same** logical heading as "US Tax Summary" and merge all content (page 4 + page 5) under one heading "US Tax Summary."
- **One sheet per heading**: Output can be “one sheet per detected heading,” each sheet containing that heading’s tables in order. That matches the QB workbook (Overview sheet, US Tax Summary sheet, etc.) without hardcoding names — sheet name = heading (or normalized form). QB mapping then only renames when we want QB-specific labels.
- **Accuracy**: Data is extracted **by heading**: everything under "Reportable Interest" belongs to that block; nothing from "Dividends and Distributions" gets mixed in. So extraction stays accurate and grouped correctly.

**Structure (conceptual)**

- **Level 1**: Document headings (Overview, US Tax Summary, General Information, Holdings, …), with “Continued” merged into the same heading.
- **Level 2**: Under each heading, the list of **tables/sub-sections** (e.g. under US Tax Summary: Dividends and Distributions, Reportable Interest, Non-Reportable Items, Realized Capital Gains, Unrealized Gain (Loss)).

**How to implement**

1. **VL / parser**: Either (a) ask the model to output a clear hierarchy (e.g. “Heading: US Tax Summary” then “Table: Dividends and Distributions” with rows, etc.) or (b) keep current flat section list and add a **post-process**: detect heading-like section names, merge sections whose names match “X (Continued)” into “X,” and group sections by top-level heading (e.g. by page + known “Continued” pattern, or by a small set of rules: “Reportable Interest”, “Non-Reportable Items”, “Dividends and Distributions” belong under “US Tax Summary” when they appear on the same page as that title).
2. **Output**: Internal model could be `headings: [ { name, tables: [ { name, rows } ] } ]`. Excel: one sheet per `name` in `headings`, each sheet contains that heading’s `tables` in order.
3. **QB**: QB sheet names often match these headings (Overview, US Tax Summary). So “map to QB sheet names” (Phase 2) becomes “map detected heading → QB sheet name” (optional); if no mapping, sheet name = heading.

This makes **heading detection + data-under-heading** the universal backbone: extraction is accurate by heading, and sheet names come from headings (then optionally renamed for QB).

---

## Part 6: Summary Table – QB Sheet vs Source

| QB sheet | Primary source in GS PDF (first 5 pages) | Our current extraction | Phase to address |
|----------|----------------------------------------|------------------------|------------------|
| Net Assets | Not in first 5 pages (would need full statement or other docs) | — | 4 |
| Operations | Not in first 5 pages (monthly P&L) | — | 4 |
| Partner Capital | Not in first 5 pages | — | 4 |
| PLSummary / PLSummary Goldman Sachs | Overview (Portfolio Activity, Investment Results); Performance | Partial (Overview often missing; structure wrong) | 1, 2, 3 |
| Journal Entry Import | Reportable Income, Dividends, Realized/Unrealized | We extract tables but don’t generate journals | 5 |
| Journal Entries | Same as above | Same | 5 |
| Unrealized | US Tax Summary (Continued) – Current Unrealized Gain (Loss) | We extract it but don’t map to Unrealized sheet | 2, 6 |
| Change in Dividend | From accrual movements (not explicit on first 5 pages) | — | 6 |
| Change in Interest | Same | — | 6 |
| Alt Inv Transfer | Not in first 5 pages | — | 4 |
| (Implicit: Overview, US Tax Summary) | Pages 3, 4, 5 | Sections exist but naming/layout differ from QB | 1, 2 |

---

## Part 7: Recommended order of work

1. **Finish Phase 1** (extraction quality) so that a single GS PDF (first 5 pages) produces **complete, correct** JSON/Excel (Overview + full US Tax Summary + Non-Reportable; no wrong/missing values).
2. **Implement Phase 2** (map to QB sheet names and group by sheet) so that the same JSON produces an Excel with **Overview** and **US Tax Summary** (and optionally **Portfolio Information**) as separate sheets with QB-style names.
3. **Design Phase 3** (PLSummary block and column mapping) and implement for **one strategy, one period** so that one GS statement fills one block of “PLSummary Goldman Sachs”.
4. Add **Phase 5** (Journal Entry Import) as a separate mode (e.g. `--journal` flag) with a small account-mapping config, so we can test journal generation from Reportable Income + Dividends + Realized/Unrealized.
5. **Phases 4 and 6** (multi-PDF, time columns, Unrealized/Change in Dividend/Interest) once single-PDF path is stable and matches QB structure for the sheets we can populate from the first 5 pages.

This plan keeps the pipeline **universal** (any PDF → better extraction) while adding **optional** QB-specific mapping and layout so that, when the PDF is a broker/tax statement, we can approach the QB Automation Sheet structure step by step.

---

## Part 8: Data strategy — different PDFs and benchmarks to improve prompts/script

**Goal**: Use **diverse PDF data** (and, where available, PDFs + reference JSONs) to analyze our output, find failures, and improve the prompt and parser — not only tune on the single GS PDF.

### What we already have

| Data | What it is | How we use it |
|------|------------|----------------|
| **OmniDocBench** (Hugging Face: `opendatalab/OmniDocBench`) | ~1,355 **page images** + **ground-truth annotations** (layout, table regions). Not raw PDFs. | **Evaluation**: run our VL extractor on images → compare our table/section count to ground truth → get metrics. Use results to tune prompts/code. See `scripts/download_benchmark_data.py`, `scripts/run_benchmark_eval.py`, `docs/BENCHMARK_DATA_EXPLAINED.md`. |

So we already **did** set up a download path (OmniDocBench). It gives **images + labels** for **evaluation**, not a folder of PDFs. Running the benchmark gives numbers; we then improve prompts/script based on those numbers.

### Adding PDFs + reference JSON for analysis

To **analyze different PDFs and their JSONs** (and improve the script from that), we can add one or more sources of **real PDFs** with **ground-truth or example extractions** (JSON/HTML):

| Source (Hugging Face / web) | What it offers | Use |
|----------------------------|----------------|-----|
| **ICDAR-2013** (e.g. `bsmock/ICDAR-2013-Table-Competition-Corrected`) | 67 PDFs + HTML/JSON table ground truth (EU/US gov reports). | Download a small subset → run our pipeline on the PDFs (or rendered pages) → compare our JSON to reference HTML/JSON → find where we miss or misstructure tables. |
| **PubTables-1M** (subsets) | Very large set with PDFs + JSON bounding boxes + HTML table markup. | Same idea: sample a few dozen PDFs (or page images), run our extractor, compare to reference tables. |
| **Other doc-understanding benchmarks** | e.g. pdfQA annotations, table-extraction-scientific-datasets. | If they provide PDF (or image) + expected structure/QA, we can run our pipeline and compare. |

**Concrete next steps** (to do as part of the plan, before or alongside Phase 1):

1. **Run existing benchmark** (OmniDocBench): fix HF cache path on Windows if needed, then `pip install -r requirements-benchmark.txt`, `python scripts/run_benchmark_eval.py --max-samples 10 --schema-type universal`. Use the report to see where extraction fails (e.g. table detection, section count).
2. **Add a small “diverse PDF” dataset step**: script or doc that (a) downloads a **small** set of PDFs (or PDF-derived images) + reference JSON/HTML from e.g. ICDAR-2013 or a PubTables subset, (b) runs our pipeline on each, (c) optionally compares our JSON to reference (e.g. table count, key row/column overlap), (d) writes a short “failure report” (which docs, which pages, what we got vs expected). Use that report to **improve prompts and parser** (no hard-coding: improve **general** extraction rules).
3. **Iterate**: after each prompt/parser change, re-run (1) and (2) and compare results so we see improvement on diverse data, not only on the GS PDF.

### Solid plan before executing

- **Design principles** (Part 0): no hard-coding; table fidelity (structure, bold, blanks, irregular tables); performance noted for later.
- **Phases** (Parts 5–7): Phase 1 → 2 → 3 → 5 → 4 & 6; heading-based extraction as universal backbone; QB optional and config-driven.
- **Data strategy** (this part): (1) Use OmniDocBench for **evaluation metrics**. (2) Add **diverse PDFs + reference JSON** (e.g. ICDAR or PubTables subset) to **analyze and improve** prompts/script. (3) Run both before and after changes to see results.
- **Execution order**: Lock the plan (principles + phases + data) → run benchmark + optional diverse-PDF run → improve Phase 1 (prompts, parser, blanks, bold) using those results → then proceed to Phase 2, etc., and re-check with benchmark/diverse data as we go.
