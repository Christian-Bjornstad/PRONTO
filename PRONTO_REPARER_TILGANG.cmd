@echo off
setlocal
chcp 65001 >nul
echo Lukk PRONTO og Python FELLES hos alle for du fortsetter.
echo Kjor denne fra kontoen som opprettet datamappen og kan starte PRONTO.
powershell.exe -NoProfile -File "%~dp0scripts\repair_shared_access.ps1" -Apply
set "PRONTO_EXIT=%errorlevel%"
pause
exit /b %PRONTO_EXIT%
