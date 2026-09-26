@echo off
setlocal

:: ==============================================================================
:: NavTatva · TideTrace - Windows Launcher
:: ==============================================================================

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%.."
set "ROOT_DIR=%CD%"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python environment missing in .venv.
    echo Running Setup_win.bat first...
    call "%SCRIPT_DIR%Setup_win.bat"
    if not exist ".venv\Scripts\python.exe" (
        echo [ERROR] Setup failed.
        pause
        exit /b 1
    )
)

set "TIDETRACE_OFFLINE=0"
set "TIDETRACE_OPEN_METEO_LIVE=1"
if "%AISSTREAM_API_KEY%"=="" set "AISSTREAM_API_KEY=12a28c6c53e8526cfe02f279f3d9fbee137576d9"

echo ============================================================
echo  Starting TideTrace on http://127.0.0.1:8000
echo  Press Ctrl+C to stop the server.
echo ============================================================

:: Launch default browser
start "" http://127.0.0.1:8000

.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
