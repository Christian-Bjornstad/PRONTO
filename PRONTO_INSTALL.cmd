@echo off
setlocal
chcp 65001 >nul
set "PRONTO_SCRIPT=%~dp0install_python_felles.py"
if not defined PRONTO_IVANTI set "PRONTO_IVANTI=C:\Program Files (x86)\Ivanti\Workspace Control\pwrgate.exe"

if not exist "%PRONTO_SCRIPT%" goto missing_project
if not exist "%~dp0requirements-desktop.txt" goto missing_project
if not exist "%~dp0pronto_desktop\" goto missing_project
if exist "%PRONTO_IVANTI%" goto felles
if defined PRONTO_PYTHON goto custom_python
if exist "%~dp0.venv\Scripts\python.exe" goto venv_python
where py.exe >nul 2>nul
if not errorlevel 1 goto python_launcher
where python.exe >nul 2>nul
if errorlevel 1 goto missing_python
python.exe "%PRONTO_SCRIPT%"
set "PRONTO_EXIT=%errorlevel%"
goto local_done

:python_launcher
py.exe -3.14 "%PRONTO_SCRIPT%"
set "PRONTO_EXIT=%errorlevel%"
goto local_done

:venv_python
"%~dp0.venv\Scripts\python.exe" "%PRONTO_SCRIPT%"
set "PRONTO_EXIT=%errorlevel%"
goto local_done

:custom_python
if not exist "%PRONTO_PYTHON%" goto missing_python
"%PRONTO_PYTHON%" "%PRONTO_SCRIPT%"
set "PRONTO_EXIT=%errorlevel%"

:local_done
pause
exit /b %PRONTO_EXIT%

:felles
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; $p=(Resolve-Path -LiteralPath $env:PRONTO_SCRIPT).Path; $encoded=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($p)); Set-Clipboard -Value ('import runpy, base64; runpy.run_path(base64.b64decode(''' + $encoded + ''').decode(''utf-8''), run_name=''pronto_install_felles'')[''main'']()')"
if errorlevel 1 goto clipboard_failed
start "" "%PRONTO_IVANTI%" 15694
if errorlevel 1 goto felles_failed
echo Python FELLES opens through Ivanti.
echo Paste the copied command with Ctrl+V, then press Enter.
echo Close Python FELLES after installation and open PRONTO_START.cmd.
pause
exit /b 0

:missing_project
echo Cannot find the complete PRONTO project. Extract the whole project first.
pause
exit /b 1

:missing_python
echo Python 3.14 or Python FELLES was not found.
echo Set PRONTO_PYTHON to its full executable path, or open Python FELLES through Ivanti.
pause
exit /b 1

:clipboard_failed
echo Could not copy the Python FELLES command.
pause
exit /b 1

:felles_failed
echo Could not open Python FELLES through Ivanti.
pause
exit /b 1
