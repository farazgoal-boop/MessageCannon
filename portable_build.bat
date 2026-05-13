@echo off
REM Create Portable Build of MessageCannon
setlocal

echo.
echo ====================================
echo Creating Portable Build
echo ====================================
echo.

REM Create portable directory
if exist "MessageCannon_Portable\" rmdir /s /q "MessageCannon_Portable"
mkdir MessageCannon_Portable

REM Copy executable
if exist "dist\MessageCannon.exe" (
    echo Copying executable...
    copy "dist\MessageCannon.exe" "MessageCannon_Portable\"
) else (
    echo Error: dist\MessageCannon.exe not found
    echo Please run build.bat first
    exit /b 1
)

REM Copy assets
echo Copying assets...
xcopy "src\assets" "MessageCannon_Portable\assets\" /E /I /Y

REM Copy documentation
echo Copying documentation...
copy "README.md" "MessageCannon_Portable\"
copy "LICENSE" "MessageCannon_Portable\"

if %errorlevel% neq 0 (
    echo Error: failed while copying files
    exit /b 1
)

REM Create portable marker file
echo. > "MessageCannon_Portable\portable.flag"

REM Create README for portable
(
    echo MessageCannon Portable Edition
    echo =============================
    echo.
    echo This is a portable version. Simply run MessageCannon.exe
    echo All data is stored in the same folder.
    echo.
    echo System Requirements:
    echo - Windows 10/11
    echo - Active WhatsApp Account
    echo.
) > "MessageCannon_Portable\README_PORTABLE.txt"

echo.
echo ====================================
echo Portable Build Created!
echo ====================================
echo.
echo Location: MessageCannon_Portable\
echo Executable: MessageCannon_Portable\MessageCannon.exe
echo.

endlocal
