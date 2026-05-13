@echo off
REM MessageCannon Build Script for Windows
REM Creates standalone EXE using PyInstaller
setlocal

set "ROOT_DIR=%~dp0"
set "PYTHON_EXE=%ROOT_DIR%.venv\Scripts\python.exe"

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
echo MessageCannon Build Script
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
    echo Build Successful!
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

endlocal
