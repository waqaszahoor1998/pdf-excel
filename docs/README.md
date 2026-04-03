# Documentation index

Start here, then drill into references as needed.

## Essential

| Doc | Purpose |
|-----|---------|
| **[WHICH_COMMAND.md](WHICH_COMMAND.md)** | Default command (`run.py tables`), how to read JSON `meta`. |
| **[WORKFLOWS_AND_COMMANDS.md](WORKFLOWS_AND_COMMANDS.md)** | CLI commands, web routes, `meta` fields. |
| **[../README.md](../README.md)** | Install, quick start, requirements. |
| **[config/README.md](../config/README.md)** | `vl.json`, `page_to_sheet`, `qb_cleanup.json`. |

## Pipeline and format

| Doc | Purpose |
|-----|---------|
| **[PDF_JSON_FORMAT.md](PDF_JSON_FORMAT.md)** | Why JSON first, shape of `sections`, editing workflow. |
| **[GETTING_STARTED.md](GETTING_STARTED.md)** | PDF → JSON → Excel in plain language. |
| **[EXPECTED_FORMAT.md](EXPECTED_FORMAT.md)** | QB-style sheet naming and layout targets. |
| **[QB_STYLE_OUTPUT.md](QB_STYLE_OUTPUT.md)** | Merging sections, `title_to_sheet`, colors. |

## Vision / hybrid

| Doc | Purpose |
|-----|---------|
| **[HYBRID_ROUTING.md](HYBRID_ROUTING.md)** | How hybrid chooses pages for VL. |
| **[hybrid.md](hybrid.md)** | Hybrid overview. |
| **[VL_PIPELINE_AND_LIBRARIES.md](VL_PIPELINE_AND_LIBRARIES.md)** | VL pipeline vs libraries. |
| **[VL_GPU_WHY_AND_FIX.md](VL_GPU_WHY_AND_FIX.md)** | CUDA / GPU notes. |
| **[TEST_AND_SHARE.md](TEST_AND_SHARE.md)** | Testing and sharing installs. |

## Quality and meta

Validation lives in `tables_to_excel.evaluate_extraction_json_correctness`. PDF-vs-JSON audit lives in `pdf_json_audit.py` and is merged into **`meta.audit_summary`** when audit runs. **`meta.library_routing`** flags pages that may benefit from hybrid/VL.

## Historical / deep dives

Older plans, benchmarks, and analysis notes remain under **`archive/`** and **`IMPLEMENTATION_PLAN.md`** — useful for background, not required to run the tool.
