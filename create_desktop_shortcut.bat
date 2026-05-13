@echo off
REM MessageCannon Desktop Shortcut Creator
REM Run this after installation to create a desktop icon

setlocal enabledelayedexpansion

REM Try to get installation path from Registry
for /f "tokens=2*" %%a in ('reg query "HKCU\Software\MessageCannon" /v InstallPath 2^>nul ^| findstr InstallPath') do set "APP_PATH=%%b"

REM Fallback to default if not found
if "!APP_PATH!"=="" (
    set "APP_PATH=%LOCALAPPDATA%\Programs\MessageCannon"
)

REM Try portable location if app path doesn't exist
if not exist "!APP_PATH!\MessageCannon.exe" (
    set "APP_PATH=%~dp0MessageCannon_Portable"
)

REM Check if exe exists
if exist "!APP_PATH!\MessageCannon.exe" (
    echo Creating desktop shortcut...
    
    REM Use PowerShell to create the shortcut
    powershell -Command ^
        "$DesktopPath = [Environment]::GetFolderPath('Desktop'); " ^
        "$ShortcutPath = Join-Path $DesktopPath 'MessageCannon.lnk'; " ^
        "$WshShell = New-Object -ComObject WScript.Shell; " ^
        "$Shortcut = $WshShell.CreateShortCut($ShortcutPath); " ^
        "$Shortcut.TargetPath = '!APP_PATH!\MessageCannon.exe'; " ^
        "$Shortcut.IconLocation = '!APP_PATH!\assets\icons\app.ico'; " ^
        "$Shortcut.Description = 'MessageCannon - WhatsApp Bulk Messenger'; " ^
        "$Shortcut.WorkingDirectory = '!APP_PATH!'; " ^
        "$Shortcut.Save(); " ^
        "Write-Host 'Desktop shortcut created successfully!'"
    
    echo.
    echo Shortcut created on Desktop!
) else (
    echo Error: MessageCannon.exe not found at !APP_PATH!
    echo Please install MessageCannon first.
    pause
    exit /b 1
)

endlocal
