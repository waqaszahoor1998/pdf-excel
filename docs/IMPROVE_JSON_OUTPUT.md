# How to Improve JSON Output (More Accurate, Better Results)

This guide explains **what controls JSON quality** in the VL pipeline and **exactly what to change** for more accurate, consistent output.

---

## Pipeline in one line

**PDF page → image → VL model (prompt + image) → raw text → parser → post-process → JSON**

So improvements come from: (1) **prompt**, (2) **model config**, (3) **parser**, (4) **post-processing**.

---

## 1. Prompt (biggest lever)

**Where:** `extract_vl.py` — `BROKER_STATEMENT_PROMPT`, `TAX_STATEMENT_PROMPT`, `TABLE_EXTRACTION_PROMPT`

**What to do:**

- **Be explicit about structure.** The model needs: "First line = section title. Second line = column headers separated by TAB. Next lines = one row per line, TAB between cells."
- **List the sections you want.** For broker statements: "Portfolio Information", "Portfolio Activity", "Reportable Income", "Dividends and Distributions", "Reportable Interest", "US Tax Summary", "Non-Reportable Items", etc. Naming them reduces wrong titles.
- **Ask for every row and column.** "Include every row: detail rows AND total/subtotal rows." "Do not skip the last column (e.g. Year to date)."
- **Page-type specifics.** For Overview: "Portfolio Activity: all 5 rows (beginning value, interest, dividends, change, ending value). Investment Results: 4 columns × 2 rows (Current Month and Current Year)." For US Tax Summary: list the exact subsections and column headers.
- **Anti-repetition.** "Output each table exactly once. Do not repeat the same phrase in every cell and do not duplicate rows." (Already added to broker and tax prompts.)

**Override at run time:**

```bash
python -m extract_vl "file.pdf" --json out.json --prompt "Your custom prompt"
```

---

## 2. Model config

**Where:** `config/vl.json` and env vars

| Setting | Effect | Suggested |
|--------|--------|-----------|
| **max_tokens** | Max tokens per page. Too low → model cut off, missing rows. | 2048 for simple pages; **4096** for dense (Overview, US Tax Summary). |
| **temperature** | Lower = less random, fewer repeats. | **0.1** (already default). |
| **image_scale** | Resolution of page image. Higher = clearer text, more VRAM. | 2.0 default; **3.0** if small text or dense tables. |

**Change in `config/vl.json`:**

```json
{
  "max_tokens": 4096,
  "image_scale": 2.0,
  "temperature": 0.1
}
```

**Override from CLI:**

```bash
python -m extract_vl "file.pdf" --json out.json --max-tokens 4096 --image-scale 3.0
```

---

## 3. Parser

**Where:** `extract_vl.py` — `_parse_table_blocks()`, `_split_line_to_cells()`, `_vl_text_to_sections()`

**What it does:** Turns the model’s plain text (TAB- or space-separated lines) into sections with `name`, `headings`, `rows`.

**Already in place:**

- **TAB vs spaces:** If the model uses spaces instead of TABs, `_split_line_to_cells()` splits on 2+ spaces so you still get columns (e.g. "Portfolio Number    BASE CURRENCY    MANDATE NAME" → 3 columns).
- **Block detection:** Parser expects "title line → header line → data rows". Single-cell line followed by multi-column line = new table block.

**If JSON has wrong structure:**

- Check the **raw model output** (e.g. run with `--out raw.txt` and no `--json`). If the raw text is correct but JSON is wrong, the parser logic may need a tweak for that layout (e.g. multiple tables per page, or a different header pattern).
- Add logging in `_parse_table_blocks()` to see which lines are classified as title vs header vs data.

---

## 4. Post-processing (before writing JSON)

**Where:** `extract_vl.py` — `_normalize_sections()`, `_drop_repetitive_sections()`

**Already in place:**

- **Normalize:** Pads/trims every row to `column_count` so all rows have the same number of cells.
- **Drop repetitive sections:** If the model repeated the same phrase in every cell (e.g. "Portfolio Number" in every cell of every row), that section is removed. If all rows are identical, only the first row is kept.

**Optional additions (you can add in code):**

- **Merge sections:** If the same section name appears on multiple pages, merge rows and keep a `page` or `pages` field.
- **Validate shape:** For known section names (e.g. "US Tax Summary"), check expected min rows/columns and log a warning or set a `meta.validation_warnings` list in the JSON.
- **Strip footer text:** If a row looks like "Portfolio No: XXX-XX366-3" or "Page 4 of 54", you can move it to meta or drop it from table rows.

---

## 5. Schema type (which prompt + behavior)

**CLI:** `--schema-type broker_statement` or `tax_statement` or `generic`

- **broker_statement:** Best for GS/Morgan Stanley–style statements (Portfolio Information, Overview, US Tax Summary, etc.).
- **tax_statement:** Stresses US Tax Summary layout (Dividends, Reportable Interest, Non-Reportable Items, three time columns).
- **generic:** General table extraction.

Use the one that matches your PDF. For mixed documents, you could run different pages with different `--schema-type` (e.g. page 4 only with `tax_statement`) and merge JSONs in a script.

---

## 6. Quick checklist for “better JSON right now”

1. **Use the right schema:** `--schema-type broker_statement` (or `tax_statement` for tax-heavy pages).
2. **Increase tokens for dense pages:** In `config/vl.json` set `"max_tokens": 4096` (or use `--max-tokens 4096`).
3. **Re-run after prompt/parser changes:**  
   `python -m extract_vl "file.pdf" --json output/statement_8.json --max-pages 5 --schema-type broker_statement`  
   then `python run.py from-json output/statement_8.json -o output/statement_8.xlsx`.
4. **Inspect raw output if JSON is wrong:**  
   `python -m extract_vl "file.pdf" --out raw_page3.txt --max-pages 3 --page-ranges 3`  
   and compare `raw_page3.txt` to the PDF and to the JSON.
5. **Compare runs:** `python scripts/compare_vl_json.py output/statement_6.json output/statement_8.json -v` to see section/row/cell differences.

---

## 7. What was just implemented (for your current run)

- **Prompts:** Added "Output each table exactly once. Do not repeat the same phrase in every cell and do not duplicate rows" to broker and tax prompts.
- **Post-processing:** `_drop_repetitive_sections()` removes sections where every cell is identical (e.g. "Portfolio Number" repeated) and collapses sections where all rows are identical to a single row.

These reduce garbage sections and repetition in the JSON. For full accuracy you still need enough **max_tokens**, a **clear prompt** for each page type, and optionally **higher image_scale** for dense or small text.

---

## References

- **VL pipeline:** `docs/VL_PIPELINE_AND_LIBRARIES.md`
- **Config:** `config/vl.json`, env vars in `extract_vl.py` (`VL_MAX_TOKENS`, `VL_IMAGE_SCALE`, etc.)
- **Upgrades log:** `docs/UPGRADES_REPORT.md`
