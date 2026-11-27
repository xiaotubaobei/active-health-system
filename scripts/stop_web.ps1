$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PidDir = Join-Path $Root "runtime_logs\web_pids"

Write-Host "=== 关闭主动健康系统 ===" -ForegroundColor Cyan

foreach ($name in @("frontend", "backend", "pose")) {
    $pidFile = Join-Path $PidDir "$name.pid"
    if (-not (Test-Path $pidFile)) {
        Write-Host "$name：没有找到本次启动记录"
        continue
    }

    $saved = @(Get-Content $pidFile)
    $savedPid = $saved[0] -as [int]
    $process = if ($savedPid) { Get-Process -Id $savedPid -ErrorAction SilentlyContinue } else { $null }
    if ($process) {
        if ($saved.Count -lt 2 -or $process.StartTime.ToUniversalTime().Ticks -ne [long]$saved[1]) {
            Write-Host "$name：记录不匹配，未结束该进程" -ForegroundColor Yellow
            continue
        }
        Stop-Process -Id $savedPid -Force
        Write-Host "$name：已关闭" -ForegroundColor Green
    }
    else {
        Write-Host "$name：已经停止"
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}
