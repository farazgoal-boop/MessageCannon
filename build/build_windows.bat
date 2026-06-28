@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0.."

echo ============================================================
echo  MessageCannon Pro ^— Windows Build
echo  Step 1: PyInstaller (onefile EXE)
echo  Step 2: Inno Setup (installer)
echo ============================================================
echo.

:: ----- Step 1: PyInstaller -----
echo [1/2] Building EXE with PyInstaller...
pip install pyinstaller --quiet
pyinstaller --noconfirm MessageCannon_Pro.spec

if not exist "dist\MessageCannon Pro.exe" (
    echo.
    echo ERROR: PyInstaller failed — "dist\MessageCannon Pro.exe" not found.
    pause & exit /b 1
)
for %%A in ("dist\MessageCannon Pro.exe") do echo     EXE size: %%~zA bytes
echo     EXE OK.
echo.

:: ----- Step 2: Inno Setup -----
echo [2/2] Building installer with Inno Setup...

:: Common install locations for Inno Setup
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe
if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" set ISCC=C:\Program Files (x86)\Inno Setup 5\ISCC.exe

if "!ISCC!"=="" (
    echo.
    echo  WARNING: Inno Setup not found. Skipping installer creation.
    echo  Install from: https://jrsoftware.org/isinfo.php
    echo  Then re-run this script, or compile manually:
    echo    ISCC.exe build\build_windows_installer.iss
    echo.
    goto :done
)

"!ISCC!" "build\build_windows_installer.iss"
if errorlevel 1 (
    echo.
    echo ERROR: Inno Setup compilation failed.
    pause & exit /b 1
)

if exist "dist\MessageCannonPro-Setup.exe" (
    for %%A in ("dist\MessageCannonPro-Setup.exe") do echo     Installer size: %%~zA bytes
    echo     Installer OK.
) else (
    echo  WARNING: Installer not found after ISCC — check ISS output above.
)

:done
echo.
echo ============================================================
echo  Build complete. Output in: dist\
echo    - MessageCannon Pro.exe      (portable, run directly)
echo    - MessageCannonPro-Setup.exe (installer for end users)
echo ============================================================
explorer dist
pause
