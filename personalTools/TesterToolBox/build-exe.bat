@echo off
setlocal

cd /d "%~dp0"

echo Building ErrorLogClassification desktop app...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-exe.ps1"

echo.
if errorlevel 1 (
    echo Build failed. Please check the error message above.
) else (
    echo Build completed successfully.
)

echo.
pause
