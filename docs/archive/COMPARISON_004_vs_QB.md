# Comparison: Result (004) vs QB Format

**Result file:** `9004-20251231-Combined Statement-004.xlsx` (from Downloads)  
**Reference:** Project QB format (`docs/EXPECTED_FORMAT.md` + `pdf_to_qb.py` / `tables_to_excel.py`)

---

## 1. Sheet structure vs expected QB format

### Result (004) has these sheets
| Sheet | Rows | Cols |
|-------|------|------|
| PLSummary J.P. Morgan Chase | 47 | 6 |
| Account Summary | 5 | 6 |
| Asset Allocation | 31 | 20 |
| Portfolio Activity | 60 | 20 |
| Tax Summary | 14 | 20 |
| Account E79271004 | 86 | 20 |
| Account G41269004 | 641 | 20 |
| Broker Info | 24 | 20 |

### Differences from standard QB sheet list

- **Sheets in result that are not in the standard QB list**
  - `PLSummary J.P. Morgan Chase` → expected name is **`PLSummary`** (no broker suffix).
  - `Account E79271004`, `Account G41269004` → per-account sheets are valid in QB format (EXPECTED_FORMAT mentions “Account E79271004”, “Account G41269004”), so **naming is OK**.
  - `Broker Info` → extra sheet; not in the standard QB list but acceptable as metadata.

- **Standard QB sheets missing from result**
  - Period Summary, Consolidated Summary, Cash & Fixed Income, Equity Summary, Equity Detail, Net Assets, Operations, Partner Capital, Journal Entry Import, Journal Entries, Unrealized, Change in Dividend, Change in Interest, Alt Inv Transfer.
  - **Note:** Missing sheets may be correct if the source PDF (e.g. 004) does not contain those sections. So this is a **structural difference** only if the PDF actually has those sections.

**Summary:** Main naming fix: use **`PLSummary`** instead of **`PLSummary J.P. Morgan Chase`** for consistency with QB spec.

---

## 2. Data quality issues (mistakes in the result)

### Account Summary

- **Row 3 is wrong:** PDF footer/boilerplate was captured as a data row.
  - Cells contain: `36279843²000`, `"Form") will b`, `e available online`, `. If you have not`
  - This row should be **removed** (it’s not part of the Account Summary table). The next row (“ABC TR JPM Preferreds”, G41269004, …) is the correct second account.

- **Footnote/superscript in account IDs:** `E79271004¹` and `36279843²000` — the ¹/² are footnote markers. Prefer **E79271004** and the correct account number without the footnote and the stray “000”.

### Portfolio Activity

- **Split number (parenthetical negative):** Row 4 “Net Contributions/Withdrawals” has the value **(-37,303.03)** split across two cells:
  - Col D: `(37,30`
  - Col E: `3.03)`
  - This should be **one numeric cell**: **-37303.03** (or -37,303.03 displayed). Same value may appear elsewhere; any “(X,XX” and “X.XX)” pattern is a split parenthetical number.

### Asset Allocation

- **Wide empty columns:** Sheet has 20 columns; many rows have data only in the first ~5–7 columns. Rest are empty. Not wrong, but layout is wider than needed.
- **Subheader row 8:** Row 8 has “Current”, “Year-to-”, “Date” split across cells — likely one header line “Current Year-to-Date” split into multiple cells. Minor formatting/merge issue.

### Tax Summary

- **Section separator row:** Row 7 contains “— Tax Summary 2 —” (section/page break). That’s acceptable as a separator; just be aware it’s not a data row.
- Otherwise structure (accounts, totals) looks consistent.

### PLSummary J.P. Morgan Chase

- Structure (BOM, MTD, EOM, Account Name, Market Value, etc.) matches the expected PLSummary style. Only issue is the sheet name (see above).

---

## 3. Summary of mistakes and differences

| # | Location | Issue | Severity |
|---|----------|--------|----------|
| 1 | Account Summary row 3 | Footer text in table (“Form”, “available online”, “If you have not”) | **High** – delete row |
| 2 | Account Summary | Account ID “36279843²000” is corrupted (footnote + “000”); should be correct account number | **High** |
| 3 | Portfolio Activity row 4 | Net Contributions/Withdrawals value **(37,303.03)** split into “(37,30” and “3.03)” | **High** – merge into one number |
| 4 | Sheet name | “PLSummary J.P. Morgan Chase” → should be “PLSummary” for QB | **Medium** |
| 5 | Account Summary | Superscript in “E79271004¹” – strip footnote for clean ID | **Low** |
| 6 | Asset Allocation row 8 | “Year-to-” / “Date” split across cells | **Low** |

---

## 4. Reference (001) vs result (004)

- **001 (in project):** Raw extraction, one sheet per page (Page1…Page46), single-column or minimal structure — not QB-format.
- **004 (result):** QB-style sheets (Account Summary, Asset Allocation, Portfolio Activity, Tax Summary, per-account sheets, Broker Info, PLSummary). So 004 is already in the right *direction*; the issues above are **data quality and naming**, not “wrong sheet type”.

If your “QB document” is a different reference (e.g. a hand-built or correct QB workbook), share its path and we can do a cell-by-cell or sheet-by-sheet comparison next.

---

## 5. Recommended fixes in the pipeline

1. **Table detection / bounding:** Avoid capturing footer lines (“Form”, “available online”, “If you have not”) into Account Summary. Tighten table bounding or filter rows by known header/content patterns.
2. **Number parsing:** Detect parenthetical negatives that span two cells (e.g. “(37,30” + “3.03)”) and merge into one numeric value in post-processing or in the extractor.
3. **Sheet naming:** When the report type is “MTD PNL Per Trading Account Summary”, use sheet name **PLSummary** only (no “J.P. Morgan Chase” suffix) to match QB spec.
4. **Account IDs:** Strip footnote markers (¹, ²) from account number cells when writing to Excel.

If you want, the next step can be: (a) implement these fixes in `tables_to_excel.py` / `pdf_to_qb.py`, or (b) add a small script that loads 004 and the reference QB file you provide and prints a diff.
