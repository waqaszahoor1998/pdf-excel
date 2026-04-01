# config/ – what each file is for

## vl.json

This file configures **two separate things**:

### 1. Model / extraction settings (not document-specific)

These control how the vision model runs and how we parse. They are **technical parameters**, not titles or document names:

| Key | Meaning |
|-----|--------|
| **max_tokens** | Max tokens the model can generate per page (e.g. 4096). |
| **n_ctx** | Context size (KV cache). If you see "failed to find a memory slot", try 8192. |
| **n_batch** | Batch size for prompt processing. Lower (e.g. 256) can reduce memory use. |
| **image_scale** | PDF→image scale (2.0 = faster, 3.0 = sharper). |
| **max_vl_pages_per_run** | Cap on how many pages to process in one run. |
| **temperature** | Sampling temperature (0.1 = more deterministic). |
| **schema_type_default** | Default prompt type: `"universal"` (any PDF), `"broker_statement"`, `"tax_statement"`. |

You can change these without affecting sheet names.

### 2. page_to_sheet (Excel sheet names by page number)

**What it does:** When we convert JSON → Excel, each extracted section has a **page** number (from the PDF). `page_to_sheet` says: “for this **page number**, use this **Excel sheet name**.”

- Example: `"3": "Overview"` means “all sections from page 3 go into one sheet named **Overview**.”
- `"4": "US Tax Summary"` and `"5": "US Tax Summary"` mean pages 4 and 5 both go into one sheet named **US Tax Summary** (so that sheet can have content from two pages).

**Why those names are there:** They were chosen to match **one** target layout: your GS broker statement (page 1 = contents, 2 = General Information, 3 = Overview, 4–5 = US Tax Summary). So for that PDF they line up with the real structure.

**For other PDFs:**  
Those names are **not** universal. A different PDF might have different pages (e.g. page 2 = “Account Summary”). So:

- **Option A:** Edit `page_to_sheet` to match the PDF you’re using (change the names or add more page numbers).
- **Option B:** Clear `page_to_sheet` or remove it (set to `{}`). Then the code uses **section names from the document** as sheet names (no mapping). That’s the “universal” behavior: no fixed titles.
- **Option C (future):** Use different config files per document type (e.g. `vl_gs.json`, `vl_fidelity.json`) and choose which to load.

So: **vl.json is the config file for the VL pipeline.** The first part is model/extraction settings. The **page_to_sheet** part is where sheet names live; they’re in **config** (so you can change them without touching code), but the current values are tuned to one document layout. For a universal pipeline you can leave `page_to_sheet` empty and rely on section names instead.

### Lowering VL inference time

VL runs per page and can be slow (e.g. hundreds of seconds per page on GPU). To **reduce time**:

| Change | Effect | Trade-off |
|--------|--------|-----------|
| **Lower `image_scale`** (e.g. **1.5** or **1.0**) | Smaller images → less work for the model → faster. | Slightly worse readability on dense or small text. Try 1.5 first. |
| **Lower `max_tokens`** (e.g. **2048** or **1024**) | Model stops earlier → less generation time. | Very table-heavy pages might get cut off. |
| **Use hybrid** | VL runs only on "bad" pages; rest use library. | Best win: fewer VL pages. |
| **Ensure GPU** | Set `CUDA_PATH` and use a CUDA build of `llama-cpp-python`. | CPU is much slower. |

**Env overrides** (no code change): set before running Python:

- `VL_IMAGE_SCALE=1.5` – faster rendering (smaller images).
- `VL_MAX_TOKENS=2048` – cap output length.

Example (PowerShell, one-off):

```powershell
$env:VL_IMAGE_SCALE = "1.5"
$env:VL_MAX_TOKENS = "2048"
python run.py hybrid report.pdf -o output/report_hybrid.json
```

Or edit **config/vl.json**: set `"image_scale": 1.5` and `"max_tokens": 2048` for a permanent speed-oriented default.
