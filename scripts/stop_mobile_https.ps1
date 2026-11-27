$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = Join-Path $ProjectRoot "runtime_logs\mobile_https"
$StateFile = Join-Path $RuntimeRoot "services.json"
$UrlFile = Join-Path $RuntimeRoot "current_url.txt"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Write-Host "=== 主动健康系统：关闭手机 HTTPS 服务 ===" -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $StateFile -PathType Leaf)) {
    Write-Host "没有找到一键启动记录；不会结束其他 Python 或系统进程。" -ForegroundColor Yellow
    exit 0
}

try {
    $state = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
}
catch {
    throw "启动记录损坏，未执行进程结束操作：$StateFile"
}

$items = @($state.processes)
[array]::Reverse($items)
foreach ($item in $items) {
    $process = Get-Process -Id $item.id -ErrorAction SilentlyContinue
    if (-not $process) {
        Write-Host "$($item.name)：已经停止"
        continue
    }
    $actualTicks = $process.StartTime.ToUniversalTime().Ticks
    if ($actualTicks -ne [long]$item.start_time_utc_ticks) {
        Write-Host "$($item.name)：PID 已被其他进程复用，已跳过" -ForegroundColor Yellow
        continue
    }
    if ($item.name -in @('RTMPose', 'FastAPI')) {
        $port = if ($item.name -eq 'RTMPose') { 8101 } else { 8000 }
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $($item.id)" -ErrorAction SilentlyContinue
        foreach ($child in $children) {
            if ($child.Name -eq 'python.exe' -and $child.CommandLine -like "*$Python*" -and
                $child.CommandLine -match "--port\s+$port(?:\s|$)") {
                Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Stop-Process -Id $process.Id -Force
    Write-Host "$($item.name)：已关闭" -ForegroundColor Green
}

Remove-Item -LiteralPath $StateFile, $UrlFile -Force -ErrorAction SilentlyContinue
Write-Host "全部一键启动服务已关闭；数据库、上传视频和运行日志均已保留。" -ForegroundColor Green
