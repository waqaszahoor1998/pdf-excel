# PDF → JSON → Excel

## Why convert to JSON first?

1. **One format for everything**  
   The same extraction (sections, tables, rows) is stored as JSON. You can feed that into Excel, QB transform, scripts, or APIs without re-reading the PDF.

2. **Easy to play with**  
   - **Edit**: Fix a value, rename a section, or drop a row in a text editor or script.  
   - **Filter**: Keep only certain sections or rows (e.g. one account, one date range).  
   - **Transform**: Rename columns, merge sections, or reshape for another tool.  
   - **Validate**: Check totals, run simple rules, or compare two JSON files (e.g. 2024 vs 2025).

3. **Scriptable**  
   Any language (Python, Node, etc.) can read JSON, change it, and pass it on. So you can:  
   - PDF → JSON (this app)  
   - Your script: edit/filter/validate JSON  
   - JSON → Excel or QB (this app or your code)

4. **Human-readable**  
   You can open the `.json` file and see section names, headers, and rows. Easier to debug and to tweak by hand than a binary Excel file.

5. **Simpler to convert to Excel later**  
   Writing Excel from a clear structure (list of sections with `name`, `headings`, `rows`) is straightforward: one sheet per section, first row = headers, rest = data. So having JSON in that shape makes “JSON → Excel” or “JSON → QB Excel” a single, predictable step.

---

## How we convert PDF to JSON

We use the **same extraction** as for Excel: read the PDF with pdfplumber, detect sections and tables, normalize cells (numbers, dates, etc.). The result is a list of sections; each section has:

- **name** – section title (e.g. "Account Summary", "Page 5")
- **headings** – title lines above the table
- **rows** – table rows (list of lists; cells are numbers or strings)

So the JSON looks like:

```json
{
  "sections": [
    {
      "name": "Account Summary",
      "headings": ["For the Period 12/1/25 to 12/31/25", "Account Summary"],
      "rows": [
        ["Account", "Number", "Beginning Net Market Value", "Ending Net Market Value", "Change In Value"],
        ["ABC TRUST", "E79271004", 15088442.61, 15135558.04, 47115.43],
        ["ABC TR JPM Preferreds", "G41269004", 9079622.63, 9148720.94, 69098.31],
        ["Total Value", null, 24168065.24, 24284278.98, 116213.74]
      ],
      "row_count": 4,
      "column_count": 5,
      "column_headers": ["Account", "Number", "Beginning Net Market Value", "Ending Net Market Value", "Change In Value"],
      "row_headers": ["ABC TRUST", "ABC TR JPM Preferreds", "Total Value"],
      "data": [
        [15088442.61, 15135558.04, 47115.43],
        [9079622.63, 9148720.94, 69098.31],
        [24168065.24, 24284278.98, 116213.74]
      ]
    }
  ]
}
```

**Grid size:** Each section has `row_count` and `column_count` so you can verify the full table was extracted.

**Row/column mapping:** We also emit `column_headers`, `row_headers`, and `data`. The **canonical** cell key is **(row_index, column_index)**: `data[i][j]`. Headers are labels and **can repeat**; for a unique cell use (i, j). Then you can get the value at **(row_heading, column_heading)** when names are unique:

- `row_headers[i]` / `column_headers[j]` = labels (may duplicate)
- `data[i][j]` = value at (i, j) — use indices when names repeat

Example: row_heading = `"ABC TRUST"`, column_heading = `"Ending Net Market Value"` → find *i* where `row_headers[i] == "ABC TRUST"`, *j* where `column_headers[j] == "Ending Net Market Value"`, then `value = data[i][j]` (e.g. 15135558.04). That way you can map “this cell” from the PDF into QB or another sheet by heading names instead of by position.

Lookup in code (Python):

```python
def value_at(section, row_heading, column_heading):
    if "row_headers" not in section or "column_headers" not in section or "data" not in section:
        return None
    try:
        i = section["row_headers"].index(row_heading)
        j = section["column_headers"].index(column_heading)
        return section["data"][i][j]
    except (ValueError, IndexError):
        return None
```

---

## One stream (no mode choice)

There is a **single extraction path**. When you extract to Excel (QB or tables), the same run also writes a JSON file next to the Excel file (same base name, `.json`). So you get both from one action — no choosing “JSON or Excel”.

- **CLI:** `python run.py tables report.pdf` → writes `output/report.xlsx` and `output/report.json`.
- **Web:** “Extract to QB format” → downloads `report.xlsx` and writes `report.json` in the server temp dir (Excel is what you download; JSON is available if you run the same pipeline locally with the same output path).
- **JSON only:** `python run.py json report.pdf` still exists if you want only the `.json` file.

---

## How to use it

**Extract a PDF (Excel + JSON in one go):**

```bash
python run.py tables report.pdf
```

Output: `output/report.xlsx` and `output/report.json`.

To get **only** JSON (e.g. for scripting):

```bash
python run.py json report.pdf
```

**Then:** Edit/filter/transform the JSON; later we can add JSON → Excel so you go: PDF → (your edits to JSON) → Excel.

---

## Summary

| Step        | What we do |
|------------|------------|
| One stream | `run.py tables` (or QB in the app) runs extraction once and writes both `.xlsx` and `.json`. |
| Sections    | Each has `name`, `headings`, `rows`, `row_count`, `column_count`; optional `row_headers`, `column_headers`, `data` for (i,j) mapping. |
| Canonical cell | Use **(row_index, column_index)**; headers can duplicate. |
| CLI        | `python run.py tables <pdf>` (Excel + JSON); `python run.py json <pdf>` (JSON only). |
