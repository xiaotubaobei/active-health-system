@echo off
setlocal
title Active Health - Mobile HTTPS Launcher
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

if not exist "%~dp0scripts\start_mobile_https.ps1" (
  echo [ERROR] Launcher script was not found:
  echo %~dp0scripts\start_mobile_https.ps1
  echo.
  pause
  exit /b 1
)

echo PowerShell: %POWERSHELL_EXE%
echo Keep this window open until the mobile HTTPS URL is displayed.
echo.
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_mobile_https.ps1"
set "START_EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%START_EXIT_CODE%"=="0" (
  echo [START FAILED] Read the error above and this log:
  echo %~dp0runtime_logs\mobile_https\launcher.log
) else (
  echo Startup completed. Background services will keep running.
)
echo.
echo Press any key to close this window...
pause
exit /b %START_EXIT_CODE%
