# Plan: GS Statement & Where We Go Next

**Purpose:** Agree on what we’re trying to achieve and in what order **before** changing more code. No implementation in this doc — plan only.

---

## 1. Current situation (brief)

| Aspect | JPM-style PDFs (e.g. 9004-…) | GS-style PDF (e.g. XXXXX3663_GS…) |
|--------|------------------------------|-----------------------------------|
| **Text extraction** | pdfplumber gets text and tables | pdfplumber gets **no text** |
| **Fallback** | N/A | PyMuPDF used; layout-based extraction (`get_text("dict")` → rows by bbox) |
| **Output** | Structured workbook, few sheets, clean tables | 374 sections → 374 sheets; some data (e.g. Portfolio Activity with numbers) but **messy / “garbage”** |
| **User feedback** | Works | “Still garbage xlsx with no data” → then “let’s get the plan before doing anything further” |

So: **JPM path is in good shape. GS path “works” in the sense that we get an xlsx with extracted content, but the result is not acceptable** (too many sheets, layout/quality issues, possibly still missing or wrong data).

---

## 2. What “success” could mean (choose one or combine)

We need a shared definition of done for the **GS statement** (and similar PDFs where pdfplumber fails).

**Option A — “Good enough for this one PDF”**  
- One workbook that looks reasonable for `XXXXX3663_GSPrefdandHybridSecurties_2025.12_Statement.pdf`.  
- Fewer, larger sheets (e.g. by section type: Account Summary, Portfolio Activity, etc.), not 374.  
- Key tables (e.g. Portfolio Activity, Investment Results) have clear headers and numbers in the right columns.  
- No requirement to support every future “weird” PDF the same way.

**Option B — “Robust fallback for any no-text PDF”**  
- Whenever pdfplumber returns no (or almost no) text, PyMuPDF fallback runs.  
- Output is always “usable”: at least one sheet per major section, tables recognizable, no hundreds of tiny sheets.  
- May need heuristics per PDF type or a small set of “known layouts” (e.g. GS vs others).

**Option C — “Structured workbook like JPM”**  
- Same **workflow** as JPM: extract → cleanup (footer, merges, title_to_sheet) → structured workbook (e.g. config-driven sheet names, merged sections).  
- GS PDF goes through the same pipeline; only the **extraction** step differs (PyMuPDF instead of pdfplumber).  
- Result: similar feel to JPM output (sheet names, layout) where the PDF has comparable sections.

**Option D — “Don’t support GS-style PDFs for now”**  
- Document that pdfplumber-based extraction is supported; PDFs where pdfplumber gets no text are “unsupported” or “experimental.”  
- No further engineering on PyMuPDF path until we explicitly decide to support this class of PDF.

**Recommendation:** Aim for **A + C** in the short term: make the **GS statement** produce a **reasonable, structured workbook** (fewer sheets, clear tables), reusing the same cleanup/structured-output ideas we use for JPM, without promising a generic “any no-text PDF” solution yet. If that works, we can later generalize (B).

---

## 3. Why we might feel “not getting anywhere”

- **Fixing bugs vs defining success:** We fixed the duplicate/broken PyMuPDF loop and section splitting, so **data is** now extracted (e.g. Portfolio Activity with numbers). But “success” was never clearly defined for this PDF, so the result can still feel like “garbage” (374 sheets, layout, naming).
- **Two different PDF worlds:** JPM path is tuned (config, cleanup, structured workbook). GS path is “extract something and dump it”; no equivalent cleanup or structure step, so output format doesn’t match expectations.
- **No clear stopping point:** Without a written “done” criterion, we can keep tweaking extraction forever.

So the plan below focuses on **defining the target**, then **doing a minimal set of changes** to reach it, and **stopping** when the target is met.

---

## 4. Proposed plan (order of work, no code yet)

### Step 0 — Lock the target (you decide)

1. **Pick success type** for the GS statement: **A**, **C**, **A+C**, **B**, or **D** (see Section 2).  
2. **Optional:** Write 2–3 concrete checks, e.g.  
   - “Workbook has a sheet named ‘Portfolio Activity’ with a ‘Market Value’ column and at least one numeric value.”  
   - “No more than N sheets (e.g. 20–30).”  
   - “Account Summary (or equivalent) is one sheet, not split across 50.”

### Step 1 — Agree on “good output” shape

- How many sheets do we want **max** for this GS PDF? (e.g. “at most 20” or “one per real section type.”)  
- Do we want **the same** structured-workbook step as JPM (config-driven sheet names, footer cleanup, etc.), or a **simplified** version for PyMuPDF-only runs?  
- Any **naming** rule? (e.g. “Page 3” vs “Portfolio Activity” — prefer section title when we have it.)

### Step 2 — Consolidate sections (reduce 374 → N)

- Today: every ALL-CAPS short title (and every “Page N”) becomes a section → 374 sheets.  
- Change: **merge** sections into a smaller set (e.g. by section title similarity, or by “same type” rules), so we output **one sheet per logical section** (e.g. one “Portfolio Activity”, one “Investment Results”), and maybe one “Other” or “Page N” only for leftover content.  
- This is the single biggest structural change: same extraction, different **grouping** before writing Excel.

### Step 3 — Reuse cleanup and naming (optional but recommended)

- Run the **same** (or a subset of) cleanup used for JPM: footer phrases, header merges, `title_to_sheet` (so “PORTFOLIO ACTIVITY” → “Portfolio Activity” sheet name).  
- Ensures GS output **looks** like our intended format (`docs/EXPECTED_FORMAT.md`) and doesn’t feel like a raw dump.

### Step 4 — Validate and stop

- Run the pipeline on the GS PDF.  
- Check against the criteria from Step 0.  
- If met: **done** for this PDF. If not: adjust only the minimal piece (e.g. merge rules or cleanup config) and re-check.  
- Document: “GS-style PDFs (pdfplumber no text): we use PyMuPDF; output is structured into N sheets with cleanup; known limitations: …”.

---

## 5. What we are **not** doing in this plan

- **No** new extraction engines (e.g. OCR, Camelot) unless we explicitly add them later.  
- **No** “perfect” solution for every possible PDF — only a clear, achievable result for the GS statement (and a path to generalize if we want).  
- **No** more ad-hoc fixes without updating this plan or the success criteria.

---

## 6. Next action (for you)

1. Read Section 2 and **choose** Option **A**, **B**, **C**, **D**, or **A+C**.  
2. (Optional) Add 2–3 concrete acceptance checks under Step 0.  
3. Answer Step 1: max sheets, same vs simplified structure, naming preference.  
4. Then we can implement **in this order:** Step 2 (merge sections) → Step 3 (cleanup/naming) → Step 4 (validate and document). No code until you confirm the direction.

---

*Summary: We have two PDF worlds (JPM ok, GS messy). To get somewhere, we lock a clear “done” for the GS file, then do section consolidation + optional cleanup, then validate and stop. This doc is the plan; implementation follows once you’re happy with it.*
