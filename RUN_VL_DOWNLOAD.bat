@echo off
REM Download Qwen2.5-VL model (~6 GB). No need to activate venv.
cd /d "%~dp0"
"venv\Scripts\python.exe" scripts\download_qwen2vl.py
pause
