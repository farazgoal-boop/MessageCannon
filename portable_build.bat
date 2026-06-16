@echo off
REM Create Portable Build of MessageCannon
setlocal

echo.
echo ====================================
echo Creating MessageCannon Premium Portable Build
echo ====================================
echo.

REM Create portable directory
if exist "MessageCannon_Portable\" rmdir /s /q "MessageCannon_Portable"
mkdir MessageCannon_Portable

REM Copy executable
if exist "dist\MessageCannon.exe" (
    echo Copying premium executable...
    copy "dist\MessageCannon.exe" "MessageCannon_Portable\"
) else (
    echo Error: dist\MessageCannon.exe not found
    echo Please run build.bat first
    exit /b 1
)

REM Copy assets
echo Copying branded assets...
xcopy "src\assets" "MessageCannon_Portable\assets\" /E /I /Y

REM Copy documentation
echo Copying documentation...
copy "README.md" "MessageCannon_Portable\"
copy "LICENSE" "MessageCannon_Portable\"
copy "installer\ACTIVATION_NOTICE.txt" "MessageCannon_Portable\"

if %errorlevel% neq 0 (
    echo Error: failed while copying files
    exit /b 1
)

REM Create portable marker file
echo. > "MessageCannon_Portable\portable.flag"

REM Create README for portable
(
    echo MessageCannon Premium Portable Edition
    echo =====================================
    echo.
    echo This package contains the premium portable workspace for MessageCannon.
    echo Run MessageCannon.exe directly. No separate installation is required.
    echo All local app data, portable markers, and bundled assets stay with this folder.
    echo.
    echo Included in this portable package:
    echo - Premium messaging workspace UI
    echo - Persistent session support
    echo - Delivery analytics and reporting tools
    echo - Built-in activation-ready licensing flow
    echo.
    echo First launch:
    echo - Open MessageCannon.exe
    echo - The app starts with branded premium startup screens
    echo - If the 3-day trial is active, continue directly into the workspace
    echo - If the trial has expired, activate from the startup gate or Settings
    echo.
    echo System requirements:
    echo - Windows 10/11
    echo - Active WhatsApp account
    echo - Internet connection for WhatsApp Web usage
    echo.
    echo Notes:
    echo - Keep your paid activation passkey private
    echo - Moving this folder keeps the portable bundle intact
    echo - Deactivation does not reset the free trial
    echo.
) > "MessageCannon_Portable\README_PORTABLE.txt"

echo.
echo ====================================
echo Premium Portable Build Created!
echo ====================================
echo.
echo Location: MessageCannon_Portable\
echo Executable: MessageCannon_Portable\MessageCannon.exe
echo Activation Notice: MessageCannon_Portable\ACTIVATION_NOTICE.txt
echo.

endlocal
