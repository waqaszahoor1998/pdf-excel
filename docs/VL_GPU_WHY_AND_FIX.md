# Why the CUDA build fails to load and how to fix it

## Why it fails

When you run `from llama_cpp import Llama`, Python loads **llama.dll** from the package. That DLL was built with **CUDA 13.2** and depends on CUDA runtime DLLs, for example:

- **cudart64_132.dll** (CUDA runtime)
- **cublas64_13.dll** / **cublasLt64_13.dll** (cuBLAS)
- (and possibly others)

Windows looks for these in:

1. The folder that contains **llama.dll** (the package `lib` folder) — they are **not** there.
2. **PATH** — only if you add the CUDA `bin` folder to PATH **before** starting Python.
3. **DLL search path** — `llama_cpp` uses `os.add_dll_directory(CUDA_PATH + "/bin")` **only if `CUDA_PATH` is set** before the import.

So the failure is: **a dependency of llama.dll (a CUDA DLL) is not found** because either:

- **CUDA_PATH** was not set before the first `llama_cpp` import, so the package never added the CUDA `bin` folder to the DLL search path, or  
- The CUDA Toolkit on your machine does not have those runtime DLLs in `bin` (e.g. different install layout).

## Solution

### 1. Set CUDA_PATH and PATH before any import (recommended)

`llama_cpp` only calls `add_dll_directory(CUDA_PATH + "/bin")` when **CUDA_PATH** is in the environment at import time. So you must set it **before** importing `llama_cpp`.

**Option A – In the same process (e.g. in your script)**

In `extract_vl.py` we already call `_ensure_cuda_path()` before `from llama_cpp import Llama`, but we were only updating **PATH**, not **CUDA_PATH**. The loader in `llama_cpp` specifically checks **CUDA_PATH**. So we will set **CUDA_PATH** (and keep PATH) in `_ensure_cuda_path()` and ensure it runs before the first import.

**Option B – Before starting Python (so it works for any script)**

In PowerShell, **before** running any Python command:

```powershell
$env:CUDA_PATH = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2"
$env:Path = "$env:CUDA_PATH\bin;$env:Path"
python -c "from llama_cpp import Llama; print('OK')"
```

Or add **permanently** in Windows:

1. **System Properties → Environment Variables**
2. New **User** or **System** variable:  
   **Name:** `CUDA_PATH`  
   **Value:** `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2`
3. Edit **Path**, add:  
   `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2\bin`
4. Restart the terminal (and any IDE) so new env vars are picked up.

Then run your script again; the loader will see **CUDA_PATH** and add the CUDA `bin` (and `lib`) folder to the DLL search path.

### 2. If it still fails: check that the CUDA DLLs exist

Confirm the runtime is in the CUDA install:

```powershell
dir "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2\bin\cudart*.dll"
```

If that path is missing or empty, (re)install the **CUDA Toolkit 13.2** (not only the driver) and ensure the **bin** directory contains the runtime DLLs.

### 3. Do **not** switch to CPU

**Do not** uninstall the CUDA build or reinstall the CPU-only wheel (`pip install llama-cpp-python`). That removes your GPU setup and forces a long re-build of the CUDA wheel. Prefer to **fix the GPU path**:

- Set **CUDA_PATH** and add CUDA `bin` to **PATH** before starting Python (see sections 1 and 2).
- If the DLL error persists, check that the CUDA Toolkit version matches the build (e.g. 13.2) and that `bin` contains `cudart64_132.dll` (or the version you built with).
- Re-run the build script if needed: `.\scripts\build_llama_cpp_cuda.ps1` (with CUDA in PATH).

---

## How to test VL extraction (GPU)

**1. Set CUDA so the DLL loads (same terminal you’ll run the test in):**

```powershell
$env:CUDA_PATH = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2"
$env:Path = "$env:CUDA_PATH\bin;$env:Path"
```

**2. Quick sanity check (model load):**

```powershell
cd C:\Users\TechMatched\Desktop\pdf-excel-3.0
.\venv\Scripts\Activate.ps1
python -c "from llama_cpp import Llama; print('OK')"
```

If you see `OK`, the GPU build is loading. If you see a DLL error, fix CUDA_PATH/PATH or the CUDA install; do **not** reinstall the CPU wheel.

**3. Run VL on a PDF (text output):**

```powershell
python -m extract_vl "C:\path\to\your.pdf" --max-pages 2
```

You should see `INFO: Loading VL model...`, then `INFO: VL page 1/2`, `INFO: VL page 2/2`, then extracted text. Limit to 2 pages for a fast test.

**4. Run VL and get JSON (then Excel):**

```powershell
python -m extract_vl "C:\path\to\your.pdf" --json output\report.json --max-pages 2
python run.py from-json output\report.json -o output\report.xlsx
```

Check `output\report.json` and `output\report.xlsx`. Use your real PDF path instead of `C:\path\to\your.pdf`.
