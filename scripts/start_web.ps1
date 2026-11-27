param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $Root "frontend"
$Backend = Join-Path $Root "backend"
$Pose = Join-Path $Root "ai_services\pose"
$Runtime = Join-Path $Root "runtime_logs"
$PidDir = Join-Path $Runtime "web_pids"
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

New-Item -ItemType Directory -Force -Path $Runtime, $PidDir | Out-Null

function Test-HttpReady {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Wait-HttpReady {
    param(
        [string]$Name,
        [string]$Url,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpReady $Url) {
            Write-Host "[OK] $Name 已就绪" -ForegroundColor Green
            return
        }
        Start-Sleep -Milliseconds 700
    }
    throw "$Name 启动超时。请查看 runtime_logs 目录中的日志。"
}

function Save-PortOwner {
    param([int]$Port, [string]$Name)
    $owner = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty OwningProcess
    if ($owner) {
        $process = Get-Process -Id $owner -ErrorAction Stop
        Set-Content -Encoding ascii -Path (Join-Path $PidDir "$Name.pid") -Value @($owner, $process.StartTime.ToUniversalTime().Ticks)
    }
}

$mobileStateFile = Join-Path $Root 'runtime_logs\mobile_https\services.json'
if (Test-Path -LiteralPath $mobileStateFile) {
    try {
        $mobileState = Get-Content -LiteralPath $mobileStateFile -Raw | ConvertFrom-Json
        $mobileProcesses = @($mobileState.processes | Where-Object {
            $candidate = Get-Process -Id $_.id -ErrorAction SilentlyContinue
            $candidate -and $candidate.StartTime.ToUniversalTime().Ticks -eq [long]$_.start_time_utc_ticks
        })
        if ($mobileProcesses.Count -eq 4 -and $mobileState.tunnel_url -and
            (Test-HttpReady 'http://127.0.0.1:8101/estimator') -and
            (Test-HttpReady 'http://127.0.0.1:8000/health') -and
            (Test-HttpReady 'http://127.0.0.1:8080')) {
            $health = Invoke-RestMethod -Uri "$($mobileState.tunnel_url)/api/health" -TimeoutSec 6
            if ($health.status -eq 'ok') {
                Write-Host '手机 HTTPS 模式已运行，电脑可直接使用同一地址：' -ForegroundColor Green
                Write-Host $mobileState.tunnel_url -ForegroundColor Cyan
                if (-not $NoBrowser) { Start-Process $mobileState.tunnel_url }
                exit 0
            }
        }
    }
    catch {
        Write-Host '手机 HTTPS 运行记录存在，但公网地址不可用。' -ForegroundColor Yellow
    }
}

foreach ($port in @(8101, 8000, 5173)) {
    $owner = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty OwningProcess
    if ($owner) {
        throw "端口 $port 已被进程 $owner 使用。请先停止对应服务，不会接管该进程。"
    }
}

Write-Host "=== 主动健康系统快捷启动 ===" -ForegroundColor Cyan
Set-Location $Root

if (-not (Test-Path $VenvPython)) {
    Write-Host "[1/5] 首次运行：创建 Python 环境..."
    python -m venv (Join-Path $Root ".venv")
}

& $VenvPython -c "import fastapi, uvicorn, sqlalchemy, pydantic, httpx, jose, passlib, multipart" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[1/5] 首次运行：安装后端依赖（可能需要几分钟）..."
    & $VenvPython -m pip install -r (Join-Path $Backend "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "后端依赖安装失败。"
    }
}

if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Host "[2/5] 首次运行：安装前端依赖（可能需要几分钟）..."
    Push-Location $Frontend
    try {
        & npm.cmd install
        if ($LASTEXITCODE -ne 0) {
            throw "前端依赖安装失败。"
        }
    }
    finally {
        Pop-Location
    }
}
else {
    Push-Location $Frontend
    try {
        & npm.cmd run build -- --emptyOutDir 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[2/5] 前端依赖不完整，正在修复..."
            & npm.cmd install
            if ($LASTEXITCODE -ne 0) {
                throw "前端依赖安装失败。"
            }
        }
        else {
            Write-Host "[2/5] 前端依赖已存在"
        }
    }
    finally {
        Pop-Location
    }
}

$env:ENABLE_DEMO_ACCOUNTS = "true"
$env:RTMPOSE_BACKEND = "onnxruntime"

& $VenvPython -c "import cv2, onnxruntime, rtmlib" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[3/5] 首次运行：安装姿态解析依赖（可能需要几分钟）..."
    & $VenvPython -m pip install -r (Join-Path $Pose "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "姿态解析依赖安装失败。"
    }
}

if (Test-HttpReady "http://127.0.0.1:8101/estimator") {
    Write-Host "[3/5] RTMPose 已经在运行"
}
else {
    Write-Host "[3/5] 启动 RTMPose..."
    Start-Process -FilePath $VenvPython `
        -ArgumentList @("-u", "main.py") `
        -WorkingDirectory $Pose `
        -RedirectStandardOutput (Join-Path $Runtime "pose.out.log") `
        -RedirectStandardError (Join-Path $Runtime "pose.err.log") `
        -WindowStyle Hidden | Out-Null
}
Wait-HttpReady -Name "RTMPose" -Url "http://127.0.0.1:8101/estimator" -TimeoutSeconds 90
Save-PortOwner -Port 8101 -Name "pose"

if (Test-HttpReady "http://127.0.0.1:8000/health") {
    Write-Host "[4/5] 后端已经在运行"
}
else {
    Write-Host "[4/5] 启动后端..."
    Start-Process -FilePath $VenvPython `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $Backend `
        -RedirectStandardOutput (Join-Path $Runtime "backend.out.log") `
        -RedirectStandardError (Join-Path $Runtime "backend.err.log") `
        -WindowStyle Hidden | Out-Null
}
Wait-HttpReady -Name "后端" -Url "http://127.0.0.1:8000/health"
Save-PortOwner -Port 8000 -Name "backend"

if (Test-HttpReady "http://127.0.0.1:5173") {
    Write-Host "[5/5] 前端已经在运行"
}
else {
    Write-Host "[5/5] 启动前端..."
    Start-Process -FilePath "node.exe" `
        -ArgumentList @("node_modules/vite/bin/vite.js", "--host", "127.0.0.1") `
        -WorkingDirectory $Frontend `
        -RedirectStandardOutput (Join-Path $Runtime "frontend.out.log") `
        -RedirectStandardError (Join-Path $Runtime "frontend.err.log") `
        -WindowStyle Hidden | Out-Null
}
Wait-HttpReady -Name "网页" -Url "http://127.0.0.1:5173"
Save-PortOwner -Port 5173 -Name "frontend"

Write-Host ""
Write-Host "启动成功：" -ForegroundColor Green
Write-Host "  网页      http://127.0.0.1:5173"
Write-Host "  API 文档  http://127.0.0.1:8000/docs"
Write-Host "  姿态服务  http://127.0.0.1:8101/estimator"
Write-Host "  演示账号  demo / 123456"

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:5173"
}
