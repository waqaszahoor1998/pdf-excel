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

### 3. Fallback: use the CPU build

If you cannot get the CUDA DLLs found:

```powershell
pip uninstall llama-cpp-python -y
pip install llama-cpp-python
```

Then run `extract_vl` as usual; it will use the CPU (slower but no CUDA dependencies).
