$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# Local demonstration only: enable the ordinary demo account for child processes.
$env:ENABLE_DEMO_ACCOUNTS = "true"

if (-not (Test-Path "$Root\data\demo_videos\manifest.json")) {
  Write-Host "Preparing offline demo videos (first run)..."
  python "$Root\scripts\setup_offline_demo.py"
}

Write-Host "Installing backend deps..."
pip install -r backend\requirements.txt -q
Write-Host "Installing AI pose (RTMPose/rtmlib) deps..."
pip install -r ai_services\pose\requirements.txt -q

Write-Host "Starting AI stubs..."
Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoExit", "-Command", "cd '$Root'; python scripts\run_ai_stubs.py"

Start-Sleep -Seconds 2
Write-Host "Starting backend on :8000..."
Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoExit", "-Command", "cd '$Root\backend'; python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

if (Test-Path "$Root\frontend\package.json") {
  Write-Host "Starting frontend (npm install if needed)..."
  Set-Location "$Root\frontend"
  if (-not (Test-Path "node_modules")) { npm install }
  Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoExit", "-Command", "cd '$Root\frontend'; npm run dev"
}

Write-Host "Done. Open http://127.0.0.1:5173  API http://127.0.0.1:8000/docs"
