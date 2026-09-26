@echo off
setlocal enabledelayedexpansion

:: ==============================================================================
:: NavTatva · TideTrace - Windows Environment Setup
:: ==============================================================================

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%.."
set "ROOT_DIR=%CD%"

echo ============================================================
echo  NavTatva · TideTrace - Windows Automated Setup
echo ============================================================
echo Project root: %ROOT_DIR%
echo.

:: 1. Check Python
echo [1/5] Checking Python installation...
set "PY_CMD="
python --version >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else (
    py -3 --version >nul 2>nul
    if %errorlevel% equ 0 (
        set "PY_CMD=py -3"
    )
)

if "%PY_CMD%"=="" (
    echo [ERROR] Python 3 was not found in PATH.
    echo Please install Python 3.11 or 3.12 from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('%PY_CMD% -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"') do set "PY_VER=%%i"
echo Found Python %PY_VER% (%PY_CMD%)

:: 2. Setup Virtual Environment
echo.
echo [2/5] Setting up virtual environment in .venv...
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in .venv...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo Virtual environment .venv already exists.
)

set "VENV_PY=.venv\Scripts\python.exe"

:: 3. Upgrade pip & Install requirements
echo.
echo [3/5] Installing dependencies...
%VENV_PY% -m pip install --upgrade pip

if exist "requirements.txt" (
    echo Installing requirements.txt, rasterio, reportlab...
    %VENV_PY% -m pip install -r requirements.txt reportlab rasterio pytest httpx
)

echo Installing PyTorch CPU and segmentation-models-pytorch...
%VENV_PY% -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
%VENV_PY% -m pip install segmentation-models-pytorch

:: 4. Configure AISStream API Key
echo.
echo [4/5] Configuring AISStream API key...
set "KEY_DIR=%USERPROFILE%\.config\navtatva"
set "KEY_FILE=%KEY_DIR%\aisstream.key"
set "DEFAULT_KEY=12a28c6c53e8526cfe02f279f3d9fbee137576d9"

if not exist "%KEY_DIR%" mkdir "%KEY_DIR%"
if not exist "%KEY_FILE%" (
    echo %DEFAULT_KEY%> "%KEY_FILE%"
    echo API key saved to %KEY_FILE%
) else (
    echo Key file already present at %KEY_FILE%
)

:: 5. Verification
echo.
echo [5/5] Verifying installation...
%VENV_PY% -c "import app.main; from app.ml import infer; m = infer.get_model(); print('[OK] App modules loaded successfully'); print('[OK] U-Net detector loaded:', m is not None)"
if errorlevel 1 (
    echo [WARNING] Verification reported an issue. Review the output above.
)

echo.
echo ============================================================
echo  Setup completed successfully!
echo  To run the project on Windows, run:
echo    .\Setup\run_win
echo  or double-click Setup\run_win.bat
echo ============================================================
