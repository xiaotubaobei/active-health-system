# 在本机开两个窗口启动前后端（演示用，关窗口即停服务）
$Root = Split-Path $PSScriptRoot -Parent
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

Write-Host "项目根: $Root"
Write-Host "将打开 2 个 PowerShell 窗口..."
Write-Host "  页面: http://127.0.0.1:5173"
Write-Host "  API:  http://127.0.0.1:8000/docs"

Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$Root'; pip install -r ai_services\pose\requirements.txt -q; python scripts\run_ai_stubs.py"
)
Start-Sleep -Seconds 3
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$Backend'; python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
)
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$Frontend'; npm run dev"
)
