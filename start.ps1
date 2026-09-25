Set-Location -Path $PSScriptRoot
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "[ERROR] Python environment missing in .venv." -ForegroundColor Red
    exit 1
}
Write-Host "TideTrace: http://127.0.0.1:8000 - press Ctrl+C to stop." -ForegroundColor Green
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
