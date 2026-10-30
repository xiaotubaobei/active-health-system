# 完成 RepCount + InfiniteRep 离线演示：同步数据 → 校验 → 可选启动服务 → 冒烟测试
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== 1/4 同步 demo_videos + manifest ===" -ForegroundColor Cyan
python scripts\sync_demo_videos.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== 2/4 数据校验 ===" -ForegroundColor Cyan
python scripts\verify_offline_demo.py
$dataOk = ($LASTEXITCODE -eq 0)
if (-not $dataOk) {
    Write-Host "数据不足，尝试 setup_offline_demo ..." -ForegroundColor Yellow
    python scripts\setup_offline_demo.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$apiOk = $false
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/demo-videos/manifest" -UseBasicParsing -TimeoutSec 3
    $apiOk = ($r.StatusCode -eq 200)
} catch {}

if (-not $apiOk) {
    Write-Host "`n=== 3/4 启动后端 + AI 桩（新窗口）===" -ForegroundColor Cyan
    & "$Root\scripts\start_framework.ps1"
    Write-Host "等待后端就绪 ..."
    Start-Sleep -Seconds 5
} else {
    Write-Host "`n=== 3/4 后端已在 :8000 运行，跳过启动 ===" -ForegroundColor Green
}

Write-Host "`n=== 4/4 API 冒烟（manifest + 会话 finish）===" -ForegroundColor Cyan
python scripts\e2e_offline_demo.py
exit $LASTEXITCODE
