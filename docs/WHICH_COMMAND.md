# Which command should I run?

## One default

For most **text-based PDFs**:

```bash
python run.py tables path/to/file.pdf
```

Or the web app: **Library + QB** → upload PDF.

You get **Excel + JSON**. You do **not** need to run library, hybrid, and VL separately and pick one.

## How you know if the JSON is “good enough”

After the default run, open the **JSON** and check **`meta`**:

| Field | Meaning |
|--------|--------|
| **`meta.status`** / **`validation_errors`** | Internal JSON structure (rows/columns, etc.). |
| **`meta.audit_summary`** | PDF vs JSON audit + automation pass/fail + confidence (when audit ran). |
| **`meta.library_routing`** | **Library-only heuristics**: which pages look weak for text extraction; **`candidate_vl_pages`** lists pages hybrid would send to VL. |

**Correctness vs the PDF** → `audit_summary` (and strict CLI flags if you use them).  
**“Should I try hybrid?”** → `library_routing.hybrid_recommended` and `candidate_vl_pages`.

## When to use hybrid or vision

- **`meta.library_routing.hybrid_recommended`** is true **or** `audit_summary` fails **or** you know the PDF is **scanned** → run **`python run.py hybrid file.pdf -o out.json`** (needs VL installed), or use **Hybrid** / **Vision only** in the web app.

Hybrid is **not** a separate “truth”; it is **library first**, then VL **only** on pages the library flagged as bad.

## Other commands (optional)

| Command | Use when |
|---------|----------|
| `python run.py json …` | You only want JSON first (edit JSON, then `from-json`). |
| `python run.py ask …` | You want a **natural-language answer**, not full tables. |
| `populate-template` | You have a **fixed Excel template** to fill after extraction. |

## See also

- `config/README.md` — `page_to_sheet`, VL settings, QB cleanup.
- `docs/hybrid.md` — hybrid routing details.
