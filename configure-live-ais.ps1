Write-Host "NavTatva · Live AIS setup" -ForegroundColor Cyan
Write-Host "Create a free API key at https://aisstream.io, then paste it below."
Write-Host "The key is saved outside the project at ~/.config/navtatva/aisstream.key."
Write-Host ""

$key = Read-Host "AISStream API key" -AsSecureString
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($key)
$plainKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)

if ([string]::IsNullOrWhiteSpace($plainKey)) {
    Write-Host "No key entered. Nothing changed." -ForegroundColor Yellow
    exit 1
}

$destDir = Join-Path $HOME ".config\navtatva"
if (-not (Test-Path $destDir)) {
    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
}

$destFile = Join-Path $destDir "aisstream.key"
[System.IO.File]::WriteAllText($destFile, $plainKey.Trim())
Write-Host "Key successfully saved." -ForegroundColor Green
Write-Host "Check the Live AIS status in the NavTatva console within 10 seconds."
Read-Host "Press Enter to exit"
