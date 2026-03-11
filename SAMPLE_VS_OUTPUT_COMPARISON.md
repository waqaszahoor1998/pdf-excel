# Sample QB vs Our Output — Comparison

**Sample:** `QB Automation Sheet- December 2025.xlsx`  
**Our output:** From pipeline (e.g. `9004-20251231-Combined Statement-001-2.xlsx`)

---

## 1. Sheet names

| Sample QB (15 sheets) | Our output (8 sheets) | Match? |
|------------------------|------------------------|--------|
| Net Assets | — | We don’t have (PDF is broker statement, not fund accounting) |
| Operations | — | We don’t have |
| Partner Capital | — | We don’t have |
| **PLSummary** | **Period Summary** + **Account Summary** | Different naming; our content is broker summary |
| **PLSummary AB GS** | — | We don’t have (different broker) |
| **PLSummary Goldman Sachs** | — | We don’t have |
| **PLSummary J.P. Morgan Chase** | **Account Summary** + **Asset Allocation** + **Portfolio Activity** + **Tax Summary** (conceptually) | Sample = one JPM sheet with PNL layout; we have 4 separate sheets |
| PLSummary Wells Fargo | — | We don’t have |
| Journal Entry Import | — | We don’t have |
| Journal Entries | — | We don’t have |
| Unrealized | — | We don’t have |
| Change in Dividend | — | We don’t have |
| Change in Interest | — | We don’t have |
| Alt Inv Transfer | — | We don’t have |
| — | **Account E79271004** | Per-account sheet (sample has this as a block inside PLSummary JPM) |
| — | **Account G41269004** | Same |
| — | **Broker Info** | We have; sample doesn’t have a separate “Broker Info” sheet |

**Summary:** Sample is a **QB workflow template** (fund accounting + multiple brokers + journal entries). Our output is **JPM combined-statement only**, so we have fewer sheet types and different names. The closest match is **PLSummary J.P. Morgan Chase** ↔ our Account Summary + Asset Allocation + Portfolio Activity + Tax Summary (and per-account data).

---

## 2. Structure: PLSummary J.P. Morgan Chase (sample) vs our sheets

### Sample: PLSummary J.P. Morgan Chase

- **Rows 1–6:** Header block  
  - Row 1: Entity **ABC Trust**  
  - Row 2: Report title **MTD PNL Per Trading Account Summary**  
  - Row 3: Broker **J.P. Morgan Chase** (+ small numeric)  
  - Row 4: Account ID **E79271004**  
  - Rows 5–6: Blank  
- **Rows 7–8:** Column headers  
  - Row 7: **BOM**, **MTD**, **MTD**, **MTD**, **EOM** (period columns)  
  - Row 8: **Account Name**, **Market Value**, **Cash In**, **Cash Out**, **PNL**, **Market Value**  
- **Rows 9+:** Data in that column layout  
  - Investments, Cash and cash equivalents, **Totals**  
  - Then line items: Accrued Dividend, Accrued Interest, Dividend Income, Interest Income, Long term realized gain/loss, etc.  
  - Then **Balance Sheet** section: Accrued Dividend and Interest, Cash - Due from Broker, Investment in Securities, Total Asset, etc.  
- **Side-by-side blocks:** Same structure repeats in later columns for another account (e.g. G41269004).

### Our output

- **Account Summary**  
  - Row 1: **For the Period 12/1/25 to 12/31/25**  
  - Row 2: **Account Summary**  
  - Rows 3–4: Fragmented headers (Account/Summary, Investment Accou/nt(s))  
  - Rows 5–7: **Account name**, **Account #**, **Beginning**, **Ending**, **Change** (and Total Value)  
  - No BOM/MTD/EOM; no Cash In / Cash Out / PNL columns.

- **Asset Allocation**  
  - Period + “Asset Allocation” then: Equity, Cash & Fixed Income, Market Value, Accruals, Market Value with Accruals.  
  - Columns are Beginning/Ending/Change and %-type values, not BOM/MTD/EOM/PNL.

- **Portfolio Activity**  
  - Beginning Market Value, Net Contributions/Withdrawals, Income & Distributions, Change in Investment Value, Ending Market Value, Accruals.  
  - Different column set than sample’s PLSummary.

- **Tax Summary**  
  - Account-level tax summary (e.g. taxable income, gains).  
  - Structure is present but not in the same “PLSummary” grid as the sample.

**Summary:** Sample uses a **single PLSummary-style sheet** with fixed columns (BOM, MTD, EOM, Account Name, Market Value, Cash In, Cash Out, PNL) and standard row labels. We output **what’s in the PDF**: separate sections with the PDF’s own column names (Beginning/Ending/Change, etc.), so **layout and column names differ** even when the underlying numbers overlap.

---

## 3. Column layout comparison

| Concept | Sample (PLSummary JPM) | Our output |
|--------|-------------------------|------------|
| Period / time | **BOM**, **MTD**, **MTD**, **MTD**, **EOM** | “For the Period …”, “Current”, “Year-to-Date” (often split) |
| Account | **Account Name** | Account name in first column |
| Values | **Market Value**, **Cash In**, **Cash Out**, **PNL**, **Market Value** | Beginning, Ending, Change; or Market Value, Accruals, etc. |
| Row labels | Investments, Cash and cash equivalents, Totals, Accrued Dividend, Interest Income, … | Same type of labels but in different sheets (Account Summary, Asset Allocation, Portfolio Activity, Tax Summary) |
| Totals | **Totals** row with numbers in PNL column | “Total Value” (and similar) in Account Summary / other sheets |
| Balance Sheet block | Accrued Dividend and Interest, Cash - Due from Broker, Investment in Securities, Total Asset, … | We don’t produce a dedicated “Balance Sheet” block in this shape |

So: **same kind of information** (accounts, market values, income, totals), but **different sheet structure and column names** — sample = one PLSummary grid; we have multiple sections with the PDF’s wording.

---

## 4. Net Assets (sample) — we don’t have this

- Sample has **Net Assets**: firm header (Akram Fund Services), Accounting Calendar/Period/Currency, entity (AB REVOCABLE TRUST), report title **STATEMENT OF NET ASSETS | As of 12/31/2025**, then **Description | Balance** and rows (Assets, Cash & Cash Equivalents, Investment in Securities, etc.).
- Our PDF is a **broker combined statement**, not a fund **Statement of Net Assets**, so we correctly don’t produce a “Net Assets” sheet unless we add a separate mapping/template for it.

---

## 5. What matches

- **Account-level data:** Same entities (e.g. ABC Trust, E79271004, G41269004) and same kinds of numbers (market values, totals, change).
- **Numeric types:** We output numbers (not text) and handle negatives; sample also uses numbers.
- **Section ideas:** We have Account Summary, Asset Allocation, Portfolio Activity, Tax Summary; sample folds similar content into PLSummary + Balance Sheet block.
- **Colors:** We use green/orange/blue for section headers, totals, and header rows; sample uses similar highlighting.

---

## 6. Gaps / differences to “match” the sample

| Gap | Meaning |
|-----|--------|
| **Sheet naming** | Use “PLSummary J.P. Morgan Chase” (and similar) instead of Period Summary / Account Summary / Asset Allocation / etc., if we want to mirror the sample exactly. |
| **One PLSummary grid** | Merge our Account Summary + Portfolio Activity (and relevant parts of Asset Allocation / Tax Summary) into **one sheet** with columns: BOM, MTD, MTD, MTD, EOM, Account Name, Market Value, Cash In, Cash Out, PNL, Market Value. |
| **Fixed column set** | Map our “Beginning/Ending/Change” (and similar) into **BOM / MTD / EOM** and **Cash In / Cash Out / PNL** so the layout matches the sample. |
| **Row label alignment** | Use the same row labels as the sample (Investments, Cash and cash equivalents, Totals, Accrued Dividend, Interest Income, etc.) even if the PDF uses different wording; would need a mapping layer. |
| **Balance Sheet block** | Add a “Balance Sheet” subsection with Accrued Dividend and Interest, Cash - Due from Broker, Investment in Securities, Total Asset, etc., if we want to mirror that part of the sample. |
| **Header block** | Sample has firm name, address, Accounting Calendar/Period/Currency at top; we have “For the Period …” and section titles but not the same header block. |
| **Other sheet types** | Net Assets, Operations, Partner Capital, Journal Entry Import, Journal Entries, Unrealized, Change in Dividend/Interest, Alt Inv Transfer come from a different workflow (fund accounting); we’d only get those by adding separate templates or data sources. |

---

## 7. Summary table

| Aspect | Sample QB | Our output |
|--------|-----------|------------|
| **Source** | QB workflow template (fund + brokers) | JPM combined statement PDF only |
| **Sheets** | 15 (Net Assets, Operations, PLSummary variants, Journal, etc.) | 8 (Period/Account Summary, Asset Allocation, Portfolio Activity, Tax Summary, 2 per-account, Broker Info) |
| **JPM content** | One “PLSummary J.P. Morgan Chase” sheet with BOM/MTD/EOM and PNL columns | Several sheets with PDF-native sections and column names |
| **Columns** | BOM, MTD, EOM, Account Name, Market Value, Cash In, Cash Out, PNL | Beginning, Ending, Change; Market Value, Accruals; etc. |
| **Row labels** | Standard (Investments, Totals, Accrued Dividend, …) | From PDF (same ideas, different wording in places) |
| **Balance Sheet block** | Yes (in PLSummary JPM) | No |
| **Numbers** | Numeric, negatives OK | Numeric, negatives OK |
| **Colors** | Green/blue/orange for headers, totals | Same idea applied |

**Bottom line:** We are **not** producing the same **sheet layout and column set** as the sample. We are producing a **faithful extraction** of the JPM PDF into Excel (sections, numbers, labels). To **match the sample**, we’d need an extra **mapping/transform step**: same data, but reorganized into the sample’s sheet names, column layout (BOM/MTD/EOM, Cash In/Cash Out/PNL), and row labels (and optionally Balance Sheet block and header block).
