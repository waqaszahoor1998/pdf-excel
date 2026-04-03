# Output analysis: 9004-20251231-Combined Statement-001.xlsx

Analysis of the current QB-format Excel output with **mistakes** and **improvements** to implement.

---

## 1. Structural / sheet-level issues

### 1.1 Period Summary sheet (332 rows)

- **Mistake:** One giant sheet with **multiple pages concatenated**, including:
  - Repeated period title ("For the Period 12/1/25 to 12/31/25") and "Account Summary" on every page.
  - **Disclaimer/legal text** in the same rows as table data (e.g. 1099 Form availability, "INVESTMENT AND INSURANCE PRODUCTS ARE: NOT FDIC INSURED", footnote text about JPMS/FINRA/SIPC).
  - Page-break markers ("— Period Summary 2 —", "THIS PAGE INTENTIONALLY LEFT BLANK") and blank rows.
- **Effect:** Real table rows (account numbers, beginning/ending value, change) are mixed with non-table content; hard to use for automation.
- **Improvement:**  
  - **Filter rows** that are clearly non-table: disclaimer lines, "THIS PAGE INTENTIONALLY LEFT BLANK", long paragraphs.  
  - **Detect table boundary** (e.g. stop when a line is all-caps disclaimer or body text with no numbers).  
  - Optionally **split by page** and keep only the first block per logical section, or tag rows by “page” so downstream can drop duplicates.

### 1.2 Account Summary sheet (only 4 rows)

- **Mistake:** Sheet is **nearly empty**. Row 4 is a fragmented header: `Beginni`, `n`, `g`, `Ending`, `Change`, `Estimated`, `Current` — i.e. "Beginning" and "Ending" split across cells, and no data rows.
- **Effect:** This sheet is useless for QB; the real account summary data lives in **Period Summary** and in per-account sheets.
- **Improvement:**  
  - Either **populate Account Summary** from the same source as the first block of Period Summary (one clean table: Account, Beginning Net Market Value, Ending Net Market Value, Change In Value).  
  - Or **merge** the first “Account Summary” block from Period Summary into the Account Summary sheet and drop the duplicate from Period Summary.  
  - **Apply fragmentation merge** to header rows so "Beginning" / "Ending" end up in single cells.

### 1.3 Asset Allocation sheet

- **Mistake:**  
  - **Fragmented numbers:** e.g. row 4: `1,421,910.` and `03 1,494,773.17` in separate cells (should be "1,421,910.03" and "1,494,773.17").  
  - **Fragmented headers:** "Current" and "Year-to-Date" split across cells (e.g. row 9: `Current`, `Year-to-`, `Date`).  
  - **Multiple page blocks** appended ("— Asset Allocation 2 —", "— Asset Allocation 3 —") which is acceptable, but the **data within** still has fragmentation and layout noise.
- **Improvement:**  
  - **Run merge logic** on every table row (including text-extracted tables), not only on `find_tables()` output.  
  - **Extend merge patterns:** e.g. "03 1,494,773.17" → treat "03" as decimal suffix of previous "1,421,910." and "1,494,773.17" as next value; or split "03 1,494,773.17" into two numeric cells.  
  - Normalize **header line** so "Current Year-to-Date" is one column header where appropriate.

### 1.4 Portfolio Activity, Tax Summary

- **Mistake:** Similar fragmentation and multi-page concatenation; column alignment can be wrong so that values sit in wrong columns (e.g. a number under "Change" might appear under "Ending").
- **Improvement:** Same as above: **merge fragmented cells**, **filter non-table lines**, and **align columns** to a known header template (e.g. Beginning, Ending, Change, Period, YTD) so values land in the right place.

### 1.5 Per-account sheets (Account E79271004, Account G41269004)

- **Mistake:**  
  - **Very long** (hundreds of rows) with **repeated section headers** and page-break markers ("— ABC TR ACCT. G41269004_11 —").  
  - **Mixed sections** in one sheet: e.g. Account Summary, Tax Summary, Cost Summary, and other blocks all in one table so that **Tax Summary** rows (Domestic Dividends, Interest Income, etc.) appear **inside** the same grid as Account Summary, with headers like "Tax Summary\nP", "eriod Value", "Value" fragmented.  
  - **Duplicate titles** ("Account Summary", "Account Summary\nCONTINUED", "JPM Preferreds", "For the Period...") repeated many times.
- **Effect:** Hard to parse programmatically; one would need to re-detect section boundaries and split again.
- **Improvement:**  
  - **Split by section** when building the QB workbook: e.g. for "Account E79271004", emit one block for "Account Summary", one for "Asset Allocation", one for "Tax Summary", etc., instead of one long stream.  
  - **Drop or collapse** repeated page headers and "CONTINUED" lines.  
  - **Apply merge** to headers and numbers so "Period Value", "Year-to-Date Value", "ST Realized Gain/Loss" are single cells.

### 1.6 Broker Info sheet

- **Mistake:**  
  - **Table of Contents** and **contact cards** mixed: e.g. "Table of ContentsPage", "Account Summary2", "Holdings", "Cash & Fixed Income5", "Portfolio Activity7" in the same column as names/roles.  
  - **Concatenated text:** "J.P. Morgan Team" and "Table of ContentsPage" in one cell; addresses split across cells inconsistently.
- **Improvement:**  
  - **Detect TOC vs contact block** (e.g. by line pattern or position).  
  - **Emit separate areas** or columns: e.g. "Contact" table (Name, Role, Phone) vs "TOC" (Section, Page).  
  - **Merge address lines** into one cell per address instead of splitting mid-word.

---

## 2. Cell- and value-level issues

### 2.1 Header fragmentation

- **Mistake:** Headers like "Beginning", "Ending", "Change In Value", "Current Year-to-Date", "Account Number" are split into multiple cells ("Beginni", "n", "g"; "Ending"; "Change Starton" (wrong); "Year-to-", "Date"; "Account S", "ummar", "y").
- **Improvement:**  
  - **Apply `_merge_fragmented_row` (or equivalent) to all rows** from extraction, not only those from `find_tables()`.  
  - **Add merge rules** for short fragments (e.g. single letter "n", "g") when the previous cell ends with a letter and the next is a continuation of a word (e.g. "Beginni" + "n" + "g" → "Beginning").  
  - **Column header normalization:** map known fragments to canonical headers (e.g. "Beginni" + "ng" → "Beginning", "Change Starton" → "Change In Value") so QB logic can recognize columns.

### 2.2 Number fragmentation and wrong type

- **Mistake:**  
  - Numbers split: "15,088,442." and "61" instead of 15088442.61; "1,421,910." and "03 1,494,773.17" instead of two clear values.  
  - Some numeric cells are **text** (e.g. "15,088,442.61" with comma) so Excel formulas don’t treat them as numbers.  
  - Occasional **wrong decimal places** (e.g. "47,115.434" instead of 47,115.43).
- **Improvement:**  
  - **Merge numeric fragments** in the extraction/merge step (already partly done; extend to all table sources).  
  - **Coerce to number** when writing to Excel: strip "$", ",", then `float()`/`int()` and write as number type.  
  - **Validate decimals** (e.g. at most 2 decimal places for currency) and fix or flag (e.g. 47,115.434 → 47,115.43).

### 2.3 Column bleed (non-table text in table rows)

- **Mistake:** Table rows contain **adjacent PDF text** (e.g. 1099 disclaimer, "Consolidated", "Forms 1099 Tax", "Reporting Statement", "e available online") in the same row as account numbers and values.
- **Improvement:**  
  - **Table boundary detection:** stop adding cells when the next “column” is long prose or all-caps disclaimer.  
  - **Column count:** if the canonical table has N columns (e.g. 5 for Account Summary), trim or drop cells beyond N, or put them in a separate “Notes” column.  
  - **Heuristic:** if a cell has no digits and is long (>40 chars) or looks like sentence, treat as non-table and don’t put it in the main data columns.

---

## 3. Summary table

| Area              | Mistake                                                                 | Improvement |
|-------------------|-------------------------------------------------------------------------|-------------|
| Period Summary    | Disclaimer/text mixed with table; page breaks; duplicate titles         | Filter non-table rows; detect table boundary; optional page de-dup |
| Account Summary   | Nearly empty; fragmented header only                                   | Fill from Period Summary block or merge; apply header merge |
| Asset Allocation  | Number/header fragmentation; multi-block OK but noisy                   | Apply merge to all rows; extend decimal/header merge rules |
| Portfolio/Tax     | Same fragmentation and column alignment                               | Merge fragments; align to standard columns |
| Per-account       | One long sheet; mixed sections; repeated headers                       | Split by section; drop page-header duplicates; merge cells |
| Broker Info       | TOC and contacts mixed; concatenated text                              | Separate TOC vs contact; merge address lines |
| Headers           | "Beginning", "Year-to-Date", etc. split across cells                   | Apply merge everywhere; optional header normalization map |
| Numbers           | Split across cells; stored as text; wrong decimals                     | Merge; coerce to number in Excel; validate/correct decimals |

---

## 4. Recommended implementation order

1. **Apply `_merge_fragmented_row` (and improved rules) to all extracted table rows**, including tables built from text-line fallback, so every sheet benefits.
2. **Extend merge patterns:** single-letter and two-letter word continuations; "num." + "digits" + " next_num" so two numbers in one cell are split correctly.
3. **Filter non-table rows** when building Period Summary and similar sheets (drop disclaimer, blank page, long prose).
4. **Normalize numeric output:** strip "$", ",", coerce to float/int when writing cells; fix 2-decimal currency.
5. **Account Summary:** either populate from first Account Summary block or merge that block into Account Summary and remove from Period Summary.
6. **Per-account sheets:** split content by section title (Account Summary, Asset Allocation, Tax Summary, etc.) and write one block per section; drop repeated "CONTINUED" and page-only headers.
7. **Broker Info:** separate TOC from contact table; merge address fragments into one cell per address.

After these changes, re-run the pipeline on `9004-20251231-Combined-Statement-001.pdf` and compare the new Excel output to this analysis to confirm improvements.
