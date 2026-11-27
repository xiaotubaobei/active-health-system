@echo off
setlocal
title Active Health - Stop Desktop
cd /d "%~dp0"
set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
where pwsh.exe >nul 2>&1
if not errorlevel 1 set "POWERSHELL_EXE=pwsh.exe"
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_web.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
echo Press any key to close this window...
pause >nul
exit /b %EXIT_CODE%
