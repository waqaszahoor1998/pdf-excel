# Getting started

## Main idea: PDF → JSON → Excel

1. The pipeline extracts **structured sections** (headings + table rows) from the PDF.
2. That becomes **canonical JSON** (`sections` + `meta`).
3. Excel is **built from that JSON** (QB-style sheets, merges, formatting).

So the JSON is the single intermediate you can inspect, edit, or feed to other tools.

## Default command (digital PDFs)

```bash
python run.py tables path/to/report.pdf
```

Outputs typically include **`output/report.xlsx`** and **`output/report.json`**. Open the JSON and read **`meta`** for validation, audit (if enabled), and **`library_routing`** hints.

## Web app

```bash
flask --app app run
```

Open **http://127.0.0.1:5000**. Choose **Library + QB** for the same default pipeline, or **Hybrid** / **Vision only** when the VL stack is installed and the PDF is hard or scanned.

## Learn more

- **[WHICH_COMMAND.md](WHICH_COMMAND.md)** — command choice and `meta` fields.  
- **[WORKFLOWS_AND_COMMANDS.md](WORKFLOWS_AND_COMMANDS.md)** — full command list.  
- **[PDF_JSON_FORMAT.md](PDF_JSON_FORMAT.md)** — JSON shape and why it exists.
