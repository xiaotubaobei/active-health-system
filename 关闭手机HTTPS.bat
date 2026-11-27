@echo off
setlocal
title Active Health - Stop Mobile HTTPS
cd /d "%~dp0"

set "POWERSHELL_EXE="
where pwsh.exe >nul 2>&1
if not errorlevel 1 set "POWERSHELL_EXE=pwsh.exe"
if not defined POWERSHELL_EXE if exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

if not defined POWERSHELL_EXE (
  echo [ERROR] PowerShell was not found.
  echo.
  pause
  exit /b 1
)

"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_mobile_https.ps1"
set "STOP_EXIT_CODE=%ERRORLEVEL%"
echo.
echo Press any key to close this window...
pause
exit /b %STOP_EXIT_CODE%
