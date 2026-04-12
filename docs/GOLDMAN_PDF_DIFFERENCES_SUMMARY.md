# Goldman PDFs – concise differences summary

Only shows **differences** (wording or header-row changes) for the 6 PDFs.
Format per cell: `label (page) / header-snippet` when available.

## PDFs (columns)
- `XXXXX3663_GSPrefdandHybridSecurties_2025.12_Statement.pdf`
- `XXXXX3671_GSMuniFI_2025.12_Statement.pdf`
- `XXXXX3655_GSMuniFIUShrtDur_2025.12_Statement.pdf`
- `XXXXX3705_AlanBrayninAdminTrCashMgmt_2025.12_Statement.pdf`
- `XXXXX3713_GSGovFIShrtDur_2025.12_Statement.pdf`
- `XXXXX3879_AlanBrayninAdminTrustSelfDirected_2025.12_Statement.pdf`

## Differences matrix (top keys)

|Key|…3663_GSPrefdandHybridSecurties|…3671_GSMuniFI|…3655_GSMuniFIUShrtDur|…3705_AlanBrayninAdminTrCashMgmt|…3713_GSGovFIShrtDur|…3879_AlanBrayninAdminTrustSelfDirected|
|---|---|---|---|---|---|---|
|portfolio activity|—|—|PORTFOLIO ACTIVITY (p3) / MARKET VALUE AS OF DECEMBER 01, 2025|PORTFOLIO ACTIVITY (p3) / Market Value / Ending|PORTFOLIO ACTIVITY (p3) / MARKET VALUE AS OF DECEMBER 01, 2025 / [ID]|PORTFOLIO ACTIVITY (p3) / Market Value / Ending|
|reportable income|—|—|REPORTABLE INCOME (p4,9) / Current Month / Quarter to Date / Year to date|REPORTABLE INCOME (p4,9) / Current Month / Quarter to Date / Year to date|REPORTABLE INCOME (p4,11) / Current Month / Quarter to Date / Year to date|REPORTABLE INCOME (p4,8) / Current Month / Quarter to Date / Year to date|
|reportable interest|—|—|REPORTABLE INTEREST (p4) / Interest Earned|REPORTABLE INTEREST (p4) / Bank Interest / [ID] / [ID] / [ID]|REPORTABLE INTEREST (p4) / Corporate Interest|REPORTABLE INTEREST (p4) / Bank Interest / [ID] / [ID]|
|annual percentage yield (apy) earned|—|—|ANNUAL PERCENTAGE YIELD (APY) EARNED (p8) / INTEREST EARNED ON BANK DEPOSIT / [ID]|ANNUAL PERCENTAGE YIELD (APY) EARNED (p8) / INTEREST EARNED ON BANK DEPOSIT / [ID] / [ID]|ANNUAL PERCENTAGE YIELD (APY) EARNED (p10) / INTEREST EARNED ON BANK DEPOSIT / [ID] / [ID]|ANNUAL PERCENTAGE YIELD (APY) EARNED (p7) / INTEREST EARNED ON BANK DEPOSIT / [ID]|
|bank interest|—|—|BANK INTEREST (p19) / GOLDMAN SACHS BANK USA DEPOSIT (BDA) / [DATE] / [ID] / [ID]|BANK INTEREST (p9) / GOLDMAN SACHS BANK USA DEPOSIT (BDA) / [DATE] / [ID] / [ID]|BANK INTEREST (p11-12) / GOLDMAN SACHS BANK USA DEPOSIT (BDA) / [DATE] / [ID] / [ID]|BANK INTEREST (p8) / Prepaid Interest / Accretion/|
|dividends and distributions|—|—|—|DIVIDENDS AND DISTRIBUTIONS (p4) / Non-Qualified US Dividends / [ID] / [ID] / [ID]|DIVIDENDS AND DISTRIBUTIONS (p4) / Non-Qualified US Dividends|DIVIDENDS AND DISTRIBUTIONS (p4) / Qualified US Dividends / [ID] / [ID] / [ID]|
|cash deposit|—|—|CASH DEPOSIT (p53) / Trfr To AcctN TR CASH MG / [DATE] / CASH WITHDRAWAL / -[ID]|CASH DEPOSIT (p11,13) / TRANS TO ACCT 032TRUS / [DATE] / CASH WITHDRAWAL / -[ID]|—|—|
|goldman sachs bank usa deposit (bda)|—|—|GOLDMAN SACHS BANK USA DEPOSIT (BDA) (p8) / AVERAGE DAILY BALANCE / [ID]|GOLDMAN SACHS BANK USA DEPOSIT (BDA) (p8) / AVERAGE DAILY BALANCE / [ID] / [ID]|GOLDMAN SACHS BANK USA DEPOSIT (BDA) (p10) / AVERAGE DAILY BALANCE / [ID] / [ID]|GOLDMAN SACHS BANK USA DEPOSIT (BDA) (p7) / AVERAGE DAILY BALANCE / [ID] / [ID]|
|complaints|—|—|COMPLAINTS (p60) / Portfolio No: XXX-XX365-5 / Page 60 of 61|COMPLAINTS (p16) / Portfolio No: XXX-XX370-5 / Page 16 of 17|COMPLAINTS (p21) / Portfolio No: XXX-XX371-3 / Page 21 of 22|COMPLAINTS (p12) / Portfolio No: XXX-XX387-9 / Page 12 of 13|

## Notes

- If a column shows `—`, that section/header was not detected for that PDF (or had no clean header row).
- Two PDFs may look very different if their extracted section labels are generic (e.g. `Tabula_*`).
