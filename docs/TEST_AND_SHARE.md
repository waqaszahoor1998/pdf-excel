# How to test everything & how to share the software

---

## Part 1: How to test

Use a **virtual environment** and run from the project root. All commands assume you're in the project folder (e.g. `C:\Users\TechMatched\Desktop\pdf-excel-3.0`).

### 1. Test the main pipeline (digital PDFs, no model)

For PDFs that have **selectable text** (digital/native PDFs), you don't need the VL model.

**Setup (once):**
```powershell
cd C:\Users\TechMatched\Desktop\pdf-excel-3.0
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Test:**
```powershell
# Replace with your PDF path
python run.py tables "path\to\report.pdf"
```
- Output: `output\report.xlsx` and `output\report.json`.
- Open the Excel file: one sheet per section, headers and rows.

**JSON only, then Excel:**
```powershell
python run.py json "path\to\report.pdf"
python run.py from-json output\report.json -o output\report.xlsx
```

**Web app (same pipeline):**
```powershell
flask --app app run
```
Open http://127.0.0.1:8003 → upload PDF → Extract to Excel (port from `.flaskenv`; override with `FLASK_RUN_PORT` or `flask --port`).

---

### 2. Test the VL pipeline (scanned / image-only PDFs)

Use this when the PDF is **scanned** (no selectable text) or when the main pipeline returns little useful data.

**Setup (once):**
```powershell
cd C:\Users\TechMatched\Desktop\pdf-excel-3.0
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-vl.txt
python scripts/download_qwen2vl.py
```
- This downloads the Qwen2.5-VL model + mmproj (~4–5 GB) into `models/qwen2.5-vl-7b/`.
- **GPU:** If you use CUDA, build the GPU wheel first (see `docs/VL_GPU_WHY_AND_FIX.md`). Set `CUDA_PATH` and add CUDA `bin` to `PATH` before running.

**Quick check that the model loads:**
```powershell
python -c "from llama_cpp import Llama; print('OK')"
```
If you see `OK`, the library loads. If you see a DLL error, fix CUDA (see `docs/VL_GPU_WHY_AND_FIX.md`).

**Test VL (2 pages, text only):**
```powershell
python -m extract_vl "path\to\scanned.pdf" --max-pages 2
```
You should see log lines like `VL page 1/2`, `VL page 2/2`, then extracted text.

**Test VL → JSON → Excel (two commands):**
```powershell
# 1. PDF → JSON (use --max-pages N to process only the first N pages, e.g. 5)
python -m extract_vl "path\to\scanned.pdf" --json output\report.json --max-pages 5

# 2. JSON → Excel
python run.py from-json output\report.json -o output\report.xlsx
```
- Check `output\report.json`: sections with `name`, `headings`, `rows`.
- Check `output\report.xlsx`: one sheet per section, first row = headers, then data.

---

### 3. Test checklist

| What | Command / action | Expected |
|------|------------------|----------|
| Digital PDF → Excel | `python run.py tables report.pdf` | `output\report.xlsx` + `output\report.json` |
| Digital PDF → JSON only | `python run.py json report.pdf` | `output\report.json` |
| JSON → Excel | `python run.py from-json output\report.json -o out.xlsx` | `out.xlsx` |
| Web app | `flask --app app run` → upload PDF → Extract | Excel download |
| VL model loads | `python -c "from llama_cpp import Llama; print('OK')"` | `OK` |
| Scanned PDF → text | `python -m extract_vl scanned.pdf --max-pages 2` | Text printed |
| Scanned PDF → JSON + Excel | `python -m extract_vl scanned.pdf --json output\report.json` then `run.py from-json ...` | JSON + xlsx in `output\` |

---

## Part 2: How to share the software with someone

Give them the **project folder** (or a zip / clone) and these steps. They can run the **main pipeline** without the model; the **VL pipeline** needs the model (and optionally GPU).

### What they need

- **Python 3.10+**
- **For main pipeline only:** no API key, no model. Just Python + dependencies.
- **For VL (scanned PDFs):** ~4–5 GB disk for the model; NVIDIA GPU + CUDA optional but recommended (faster).

---

### Option A: Main pipeline only (digital PDFs)

They only need to extract tables from **digital** PDFs (exported from Word, Excel, etc.):

1. **Get the project** (folder or zip).
2. **Terminal in project folder:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. **Run:**
   ```powershell
   python run.py tables "path\to\file.pdf"
   ```
   Output: `output\file.xlsx` and `output\file.json`.

Or run the web app:
```powershell
flask --app app run
```
Then open http://127.0.0.1:8003 and upload a PDF.

**Optional:** Copy `.env.example` to `.env` if they want to change `OUTPUT_DIR` or use Ask AI (then they need `ANTHROPIC_API_KEY`).

---

### Option B: Full setup including VL (scanned PDFs)

If they need to process **scanned** PDFs (images of pages), they need the VL model and the VL dependencies.

1. **Get the project** (same as above).
2. **Create venv and install base + VL deps:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   pip install -r requirements-vl.txt
   ```
3. **Download the model (once):**
   ```powershell
   python scripts/download_qwen2vl.py
   ```
   This downloads to `models/qwen2.5-vl-7b/` (~4–5 GB).
4. **GPU (optional but recommended):**
   - Install CUDA (e.g. 12.x or 13.x) and set `CUDA_PATH`; add CUDA `bin` to `PATH`.
   - Build GPU wheel: run `.\scripts\build_llama_cpp_cuda.ps1` with venv active (see `docs/VL_GPU_WHY_AND_FIX.md`).
   - If they skip GPU, the default pip install may be CPU-only (slower).
5. **Run VL extraction:**
   ```powershell
   python -m extract_vl "path\to\scanned.pdf" --json output\report.json --max-pages 10
   python run.py from-json output\report.json -o output\report.xlsx
   ```

**Optional:** Copy `.env.example` to `.env`. For VL they can set:
- `QWEN2VL_MODEL_DIR=models/qwen2.5-vl-7b` (or custom path)
- Or `QWEN2VL_MODEL_PATH` and `QWEN2VL_MMPROJ_PATH` if the model is elsewhere.

---

### One-page “share” summary

**Digital PDFs (normal use):**
```text
1. Python 3.10+, project folder
2. venv + pip install -r requirements.txt
3. python run.py tables yourfile.pdf   → output\yourfile.xlsx and .json
   OR: flask --app app run → http://127.0.0.1:8003 → upload PDF
```

**Scanned PDFs (VL):**
```text
1. Above, plus: pip install -r requirements-vl.txt
2. python scripts/download_qwen2vl.py   (once, ~4–5 GB)
3. (Optional) GPU: CUDA + build_llama_cpp_cuda.ps1 — see docs/VL_GPU_WHY_AND_FIX.md
4. python -m extract_vl scanned.pdf --json output\report.json
   python run.py from-json output\report.json -o output\report.xlsx
```

Point them to:
- **This file** for testing and sharing steps.
- **`docs/VL_GPU_WHY_AND_FIX.md`** if they hit DLL/CUDA errors with the VL model.
- **`docs/VL_PIPELINE_AND_LIBRARIES.md`** for what each part does (libraries vs model, when to use VL).
