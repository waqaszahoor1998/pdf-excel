# Build llama-cpp-python from source with CUDA 13.2 (or whatever CUDA is on PATH).
# Requires: CMake (e.g. from https://cmake.org or Visual Studio), Visual Studio with C++ workload,
#            and CUDA Toolkit 13.2 installed.
#
# Run from project root with venv activated:
#   .\venv\Scripts\Activate.ps1
#   .\scripts\build_llama_cpp_cuda.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path "$root\venv\Scripts\pip.exe")) {
    Write-Host "Run this script from the repo root or ensure venv exists at $root\venv"
    exit 1
}

# Ensure Visual Studio C++ dev environment is in PATH (needed for nvcc / CMake CUDA toolset)
$vsDevBat = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"
if (Test-Path $vsDevBat) {
    $vsEnv = cmd /c "`"$vsDevBat`" -no_logo -arch=amd64 && set"
    foreach ($line in $vsEnv) {
        if ($line -match '^([^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
    Write-Host "Injected Visual Studio 2022 Build Tools environment"
}

# CUDA 13.2 paths (so MSBuild CUDA targets get CudaToolkitDir)
$cudaRoot = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2"
$cudaBin = "$cudaRoot\bin"
if (Test-Path $cudaBin) {
    $env:Path = "$cudaBin;$env:Path"
    $env:CUDA_PATH = $cudaRoot
    Write-Host "Added CUDA 13.2 to PATH and CUDA_PATH"
}
# MSBuild CUDA targets read CudaToolkitDir from CUDA_PATH; pip build isolation strips env.
# So we must use --no-build-isolation so the build subprocess sees CUDA_PATH.
$env:CUDA_PATH_V13_2 = $cudaRoot
# CMake
$cudaRootCmake = $cudaRoot -replace '\\', '/'
# Use Ninja generator so CMake uses nvcc directly (VS generator has "No CUDA toolset found" on Windows)
$ninjaPath = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja"
if (Test-Path $ninjaPath) { $env:Path = "$ninjaPath;$env:Path"; Write-Host "Added Ninja to PATH" }
# CUDA 13.2 CCCL headers require MSVC conforming preprocessor (/Zc:preprocessor)
$env:CMAKE_ARGS = "-G Ninja -DGGML_CUDA=on -DCUDAToolkit_ROOT=`"$cudaRootCmake`" -DCMAKE_CUDA_COMPILER=`"$($cudaRootCmake)/bin/nvcc.exe`" -DCMAKE_CUDA_FLAGS=`"-Xcompiler=/Zc:preprocessor`""
$env:FORCE_CMAKE = "1"

# PathTooLongException: pip/CMake use %TEMP%; nested paths exceed Windows 260-char limit. Use a short build root.
$shortTmp = "C:\b"
if (-not (Test-Path $shortTmp)) { New-Item -ItemType Directory -Path $shortTmp -Force | Out-Null }
$env:TEMP = $shortTmp
$env:TMP = $shortTmp
Write-Host "Using short TEMP for build: $shortTmp (avoids path-too-long errors)"

Write-Host "Installing build dependencies (for --no-build-isolation)..."
& "$root\venv\Scripts\pip.exe" install --quiet cmake scikit-build-core pyproject-metadata
Write-Host "Building llama-cpp-python with CUDA (this can take 5-15 minutes)..."
& "$root\venv\Scripts\pip.exe" install llama-cpp-python --no-cache-dir --force-reinstall --no-build-isolation
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed. Ensure CMake and Visual Studio C++ build tools are installed."
    exit $LASTEXITCODE
}
Write-Host 'Done. Test with: python -c "from llama_cpp import Llama; print(''OK'')"'
