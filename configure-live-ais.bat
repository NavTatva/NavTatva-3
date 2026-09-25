@echo off
setlocal
echo NavTatva -- Live AIS setup
echo Create an API key at https://aisstream.io, then paste it below.
echo The key is saved outside the project and picked up automatically.
echo.
set /p "AIS_KEY=AISStream API key: "
if "%AIS_KEY%"=="" (
    echo No key entered. Nothing changed.
    pause
    exit /b 1
)
if not exist "%USERPROFILE%\.config\navtatva" mkdir "%USERPROFILE%\.config\navtatva"
<nul set /p="%AIS_KEY%" > "%USERPROFILE%\.config\navtatva\aisstream.key"
set "AIS_KEY="
echo.
echo Key saved to %USERPROFILE%\.config\navtatva\aisstream.key.
echo Check the Live AIS status in the web console within 10 seconds.
pause
