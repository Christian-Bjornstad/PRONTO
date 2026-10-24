@echo off
setlocal
powershell.exe -NoProfile -File "%~dp0scripts\create_desktop_shortcut.ps1"
set "PRONTO_EXIT=%errorlevel%"
if not "%PRONTO_EXIT%"=="0" pause
exit /b %PRONTO_EXIT%
