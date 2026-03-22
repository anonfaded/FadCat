@echo off
REM FadCat CLI wrapper - routes to FadCat-CLI.exe with --cli flag
REM Located in: %APPDATA%\FadCat\
REM When %APPDATA%\FadCat\ is in PATH, users can type: fadcat [args]

cd /d "%~dp0"
FadCat-CLI.exe --cli %*
