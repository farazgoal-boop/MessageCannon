@echo off
REM MessageCannon Build Script for Windows
REM Creates EXE, portable bundle, and installer when tooling is available
setlocal

set "ROOT_DIR=%~dp0"
set "PYTHON_EXE=%ROOT_DIR%.venv\Scripts\python.exe"
set "ISCC_EXE="

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Virtual environment Python not found at "%PYTHON_EXE%"
    echo Create venv first: python -m venv .venv
    exit /b 1
)

for /f "tokens=1,* delims==" %%A in ('findstr /b /c:"home" "%ROOT_DIR%.venv\pyvenv.cfg"') do set "PY_BASE=%%B"
if defined PY_BASE (
    set "PY_BASE=%PY_BASE:~1%"
)
set "TCL_DIR=%PY_BASE%\tcl\tcl8.6"
set "TK_DIR=%PY_BASE%\tcl\tk8.6"

if exist "%TCL_DIR%" set "TCL_LIBRARY=%TCL_DIR%"
if exist "%TK_DIR%" set "TK_LIBRARY=%TK_DIR%"

echo.
echo ====================================
echo MessageCannon Premium Build Pipeline
echo ====================================
echo.

REM Check if PyInstaller is installed
"%PYTHON_EXE%" -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    "%PYTHON_EXE%" -m pip install pyinstaller
)

REM Create dist directory if not exists
if not exist "dist\" mkdir dist

REM Detect Inno Setup compiler for one-shot installer builds
for /f "delims=" %%I in ('where iscc 2^>nul') do (
    if not defined ISCC_EXE set "ISCC_EXE=%%I"
)
if not defined ISCC_EXE if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_EXE=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC_EXE=C:\Program Files\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%USERPROFILE%\AppData\Local\Programs\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%USERPROFILE%\AppData\Local\Programs\Inno Setup 6\ISCC.exe"

set "ICON_ARG="
if exist "src\assets\icons\app.ico" (
    set "ICON_ARG=--icon src\assets\icons\app.ico"
)

REM Build the EXE
echo.
echo Building MessageCannon EXE...
echo.

"%PYTHON_EXE%" -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "MessageCannon" ^
    --add-data "src\assets;assets" ^
    --add-data "src\database\schema.sql;src\database" ^
    --add-data "docs;docs" ^
    --add-data "README.md;." ^
    --hidden-import "customtkinter" ^
    --hidden-import "pandas" ^
    --hidden-import "openpyxl" ^
    --hidden-import "pywhatkit" ^
    --hidden-import "selenium" ^
    --collect-submodules "selenium" ^
    --hidden-import "qrcode" ^
    --hidden-import "PIL" ^
    --hidden-import "reportlab" ^
    --hidden-import "schedule" ^
    --exclude-module "pytest" ^
    --clean ^
    --distpath "dist" ^
    --workpath "build" ^
    --specpath "." ^
    %ICON_ARG% ^
    "src\main.py"

if %errorlevel% equ 0 (
    echo.
    echo ====================================
    echo EXE Build Successful!
    echo ====================================
    echo.
    echo Executable created: dist\MessageCannon.exe
    echo.
) else (
    echo.
    echo ====================================
    echo Build Failed!
    echo ====================================
    echo.
    exit /b 1
)

echo ====================================
echo Creating Portable Premium Bundle
echo ====================================
call "%ROOT_DIR%portable_build.bat"
if %errorlevel% neq 0 (
    echo.
    echo ====================================
    echo Portable Build Failed!
    echo ====================================
    echo.
    exit /b 1
)

if defined ISCC_EXE (
    echo.
    echo ====================================
    echo Building Premium Installer
    echo ====================================
    echo Using: %ISCC_EXE%
    echo.
    "%ISCC_EXE%" "%ROOT_DIR%installer\setup.iss"
    if %errorlevel% neq 0 (
        echo.
        echo ====================================
        echo Installer Build Failed!
        echo ====================================
        echo.
        exit /b 1
    )
) else (
    echo.
    echo ====================================
    echo Installer Step Skipped
    echo ====================================
    echo Inno Setup compiler not found.
    echo To build the installer later, install Inno Setup 6 and rerun build.bat
    echo.
)

echo ====================================
echo Premium Packaging Complete
echo ====================================
echo EXE: dist\MessageCannon.exe
echo Portable: MessageCannon_Portable\MessageCannon.exe
if defined ISCC_EXE echo Installer: installer\MessageCannon_Setup.exe
echo.

endlocal
