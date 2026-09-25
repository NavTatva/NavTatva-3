@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python environment missing in .venv.
    pause
    exit /b 1
)
echo TideTrace: http://127.0.0.1:8000 - press Ctrl+C to stop.
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
