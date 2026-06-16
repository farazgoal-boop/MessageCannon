@echo off
cd /d "%~dp0.."
echo Building MessageCannon Pro...
pip install pyinstaller --quiet
pyinstaller --noconfirm MessageCannon_Pro.spec
if exist "dist\MessageCannon Pro.exe" (
    echo.
    echo Build complete!
    echo File: dist\MessageCannon Pro.exe
    for %%A in ("dist\MessageCannon Pro.exe") do echo Size: %%~zA bytes
) else (
    echo BUILD FAILED - check output above.
    exit /b 1
)
pause
