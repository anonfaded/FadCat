@echo off
REM FadCat Uninstaller for Windows
REM This script will remove FadCat and optionally remove settings

echo.
echo 🗑️  FadCat Uninstaller
echo =====================
echo.

REM Check if running as admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ⚠️  This uninstaller requires Administrator privileges
    echo Attempting to elevate...
    powershell -Command "Start-Process '%~f0' -Verb runAs"
    exit /b
)

echo Removing FadCat...

REM Try to run the InnoSetup uninstaller if it exists
if exist "%APPDATA%\FadCat\uninstall.exe" (
    "%APPDATA%\FadCat\uninstall.exe" /VERYSILENT /SUPPRESSMSGBOXES
    echo ✓ Uninstaller completed
) else (
    echo ⚠️  InnoSetup uninstaller not found. Attempting manual removal...
    
    REM Remove from Program Files/AppData
    if exist "%APPDATA%\FadCat" (
        rmdir /s /q "%APPDATA%\FadCat"
        echo ✓ Removed %APPDATA%\FadCat
    )
    
    if exist "%ProgramFiles%\FadCat" (
        rmdir /s /q "%ProgramFiles%\FadCat"
        echo ✓ Removed %ProgramFiles%\FadCat
    )
    
    REM Remove PATH entry
    setlocal enabledelayedexpansion
    for /f "tokens=2*" %%a in ('reg query "HKEY_CURRENT_USER\Environment" /v PATH 2^>nul') do (
        set "path_value=%%b"
    )
    if defined path_value (
        set "path_value=!path_value:%APPDATA%\FadCat;=!"
        reg add "HKEY_CURRENT_USER\Environment" /v PATH /d "!path_value!" /f >nul
        echo ✓ Removed from PATH
    )
    endlocal
)

echo.
echo ✅ FadCat has been uninstalled successfully!
echo.
pause
