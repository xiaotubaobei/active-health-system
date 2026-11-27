param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$WorkspaceRoot = Split-Path -Parent $ProjectRoot
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$BackendRoot = Join-Path $ProjectRoot "backend"
$PoseRoot = Join-Path $ProjectRoot "ai_services\pose"
$DeployRoot = Join-Path $ProjectRoot "deploy"
$ToolsRoot = Join-Path $WorkspaceRoot "mobile-tools"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Caddy = Join-Path $ToolsRoot "caddy.exe"
$Cloudflared = Join-Path $ToolsRoot "cloudflared.exe"
$Caddyfile = Join-Path $DeployRoot "Caddyfile.mobile"
$DistRoot = Join-Path $FrontendRoot "dist"
$RuntimeRoot = Join-Path $ProjectRoot "runtime_logs\mobile_https"
$StateFile = Join-Path $RuntimeRoot "services.json"
$UrlFile = Join-Path $RuntimeRoot "current_url.txt"
$LauncherLog = Join-Path $RuntimeRoot "launcher.log"
$RunLogDir = Join-Path $RuntimeRoot ("run-" + (Get-Date -Format "yyyyMMdd-HHmmss") + "-" + $PID)
$script:StartedProcesses = @()

New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
try {
    Start-Transcript -LiteralPath $LauncherLog -Append | Out-Null
}
catch {
    # Transcript is diagnostic only; startup must still work on restricted hosts.
}

function Test-HttpReady {
    param([string]$Url, [int]$TimeoutSeconds = 3)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec $TimeoutSeconds
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
        [int]$TimeoutSeconds = 60
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpReady -Url $Url) {
            Write-Host "[OK] $Name 已就绪" -ForegroundColor Green
            return
        }
        Start-Sleep -Milliseconds 700
    }
    throw "$Name 启动超时，请查看 $RuntimeRoot 中的日志。"
}

function Save-State {
    $state = [ordered]@{
        started_at = (Get-Date).ToString("o")
        tunnel_url = if (Test-Path -LiteralPath $UrlFile) {
            (Get-Content -LiteralPath $UrlFile -Raw).Trim()
        } else {
            ""
        }
        processes = @($script:StartedProcesses)
    }
    $state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $StateFile -Encoding UTF8
}

function Start-TrackedProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory,
        [string]$LogPrefix
    )
    $process = Start-Process -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput (Join-Path $RunLogDir "$LogPrefix.out.log") `
        -RedirectStandardError (Join-Path $RunLogDir "$LogPrefix.err.log") `
        -WindowStyle Hidden `
        -PassThru
    $script:StartedProcesses += [ordered]@{
        name = $Name
        id = $process.Id
        start_time_utc_ticks = $process.StartTime.ToUniversalTime().Ticks
    }
    Save-State
    return $process
}

function Stop-StartedProcesses {
    $items = @($script:StartedProcesses)
    [array]::Reverse($items)
    foreach ($item in $items) {
        Stop-TrackedProcess -Item $item
    }
}

function Stop-TrackedProcess {
    param($Item)
    $process = Get-Process -Id $Item.id -ErrorAction SilentlyContinue
    if (-not $process -or $process.StartTime.ToUniversalTime().Ticks -ne [long]$Item.start_time_utc_ticks) { return }
    if ($Item.name -in @('RTMPose', 'FastAPI')) {
        $port = if ($Item.name -eq 'RTMPose') { 8101 } else { 8000 }
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $($Item.id)" -ErrorAction SilentlyContinue
        foreach ($child in $children) {
            if ($child.Name -eq 'python.exe' -and $child.CommandLine -like "*$Python*" -and
                $child.CommandLine -match "--port\s+$port(?:\s|$)") {
                Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Stop-Process -Id $Item.id -Force -ErrorAction SilentlyContinue
}

function Assert-File {
    param([string]$Path, [string]$Hint)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "缺少文件：$Path。$Hint"
    }
}

function Assert-PortFree {
    param([int]$Port, [string]$Name)
    $owner = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty OwningProcess
    if ($owner) {
        throw "$Name 端口 $Port 已被进程 $owner 占用。请先在原窗口按 Ctrl+C 停止旧服务。"
    }
}

function Get-ExistingState {
    if (-not (Test-Path -LiteralPath $StateFile -PathType Leaf)) {
        return $null
    }
    try {
        return Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

Write-Host "=== 主动健康系统：手机 HTTPS 一键启动 ===" -ForegroundColor Cyan

$existing = Get-ExistingState
if ($existing) {
    $valid = @($existing.processes | Where-Object {
        $candidate = Get-Process -Id $_.id -ErrorAction SilentlyContinue
        $candidate -and $candidate.StartTime.ToUniversalTime().Ticks -eq [long]$_.start_time_utc_ticks
    })
    $names = @($valid | ForEach-Object { $_.name })
    $healthy = $valid.Count -eq 4 -and ($names -contains 'RTMPose') -and
        ($names -contains 'Caddy') -and ($names -contains 'cloudflared') -and
        ($names -contains 'FastAPI')
    $healthy = $healthy -and (Test-HttpReady 'http://127.0.0.1:8101/estimator') -and
        (Test-HttpReady 'http://127.0.0.1:8080') -and (Test-HttpReady 'http://127.0.0.1:8000/health')
    if ($healthy -and $existing.tunnel_url) {
        try {
            $check = Invoke-RestMethod -Uri "$($existing.tunnel_url)/api/health" -TimeoutSec 6
            $healthy = $check.status -eq 'ok'
        }
        catch { $healthy = $false }
    }
    else { $healthy = $false }
    if ($healthy) {
        Write-Host "服务仍在运行，公网健康检查已通过。" -ForegroundColor Green
        Write-Host "电脑和手机地址：$($existing.tunnel_url)"
        exit 0
    }
    if ($valid.Count -gt 0) {
        Write-Host "旧隧道已失效，正在停止上次由本脚本启动的服务..." -ForegroundColor Yellow
        [array]::Reverse($valid)
        foreach ($item in $valid) {
            Stop-TrackedProcess -Item $item
        }
        Start-Sleep -Milliseconds 500
    }
}

Remove-Item -LiteralPath $StateFile, $UrlFile -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $RunLogDir | Out-Null

Assert-File -Path $Python -Hint "请先创建项目虚拟环境并安装依赖。"
Assert-File -Path $Caddy -Hint "请将 caddy.exe 放入 $ToolsRoot。"
Assert-File -Path $Cloudflared -Hint "请将 cloudflared.exe 放入 $ToolsRoot。"
Assert-File -Path $Caddyfile -Hint "部署配置不完整。"
foreach ($port in @(8000, 8101, 8080)) {
    $name = switch ($port) { 8000 { "FastAPI" } 8101 { "RTMPose" } 8080 { "Caddy" } }
    Assert-PortFree -Port $port -Name $name
}

try {
    if (-not $SkipBuild) {
        Write-Host "[1/5] 构建手机与电脑共用网页..."
        Push-Location $FrontendRoot
        try {
            $env:VITE_API_BASE_URL = "/api"
            $env:VITE_POSE_OFFLINE = "server"
            if (-not (Test-Path -LiteralPath (Join-Path $FrontendRoot "node_modules"))) {
                & npm.cmd ci
                if ($LASTEXITCODE -ne 0) { throw "npm ci 失败。" }
            }
            & npm.cmd run build
            if ($LASTEXITCODE -ne 0) { throw "前端构建失败。" }
        }
        finally {
            Pop-Location
        }
    }
    Assert-File -Path (Join-Path $DistRoot "index.html") -Hint "请先执行前端构建。"

    Write-Host "[2/5] 启动 RTMPose..."
    $env:RTMPOSE_BACKEND = "onnxruntime"
    $env:RTMPOSE_MODE = "balanced"
    $env:RTMPOSE_DEVICE = "cpu"
    Start-TrackedProcess -Name "RTMPose" -FilePath $Python `
        -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8101") `
        -WorkingDirectory $PoseRoot -LogPrefix "pose" | Out-Null
    Wait-HttpReady -Name "RTMPose" -Url "http://127.0.0.1:8101/estimator" -TimeoutSeconds 120

    Write-Host "[3/5] 启动 Caddy 统一入口..."
    $env:APP_DOMAIN = "http://127.0.0.1:8080"
    $env:FRONTEND_ROOT = $DistRoot.Replace("\", "/")
    $env:API_UPSTREAM = "127.0.0.1:8000"
    & $Caddy validate --config $Caddyfile --adapter caddyfile
    if ($LASTEXITCODE -ne 0) { throw "Caddy 配置校验失败。" }
    Start-TrackedProcess -Name "Caddy" -FilePath $Caddy `
        -ArgumentList @("run", "--config", $Caddyfile, "--adapter", "caddyfile") `
        -WorkingDirectory $ProjectRoot -LogPrefix "caddy" | Out-Null
    Wait-HttpReady -Name "Caddy 网页入口" -Url "http://127.0.0.1:8080" -TimeoutSeconds 45

    Write-Host "[4/5] 创建 Cloudflare Quick Tunnel..."
    $tunnelUrl = ""
    for ($attempt = 1; $attempt -le 2 -and -not $tunnelUrl; $attempt++) {
        if ($attempt -gt 1) {
            Write-Host "Cloudflare 暂时限流，等待 20 秒后重试一次..." -ForegroundColor Yellow
            Start-Sleep -Seconds 20
        }
        $tunnelProcess = Start-TrackedProcess -Name "cloudflared" -FilePath $Cloudflared `
            -ArgumentList @("tunnel", "--url", "http://127.0.0.1:8080", "--http-host-header", "127.0.0.1") `
            -WorkingDirectory $ToolsRoot -LogPrefix "cloudflared"
        $deadline = (Get-Date).AddSeconds(75)
        while ((Get-Date) -lt $deadline -and -not $tunnelUrl) {
            $logText = ""
            foreach ($logName in @("cloudflared.out.log", "cloudflared.err.log")) {
                $logPath = Join-Path $RunLogDir $logName
                if (Test-Path -LiteralPath $logPath) {
                    $logText += Get-Content -LiteralPath $logPath -Raw -ErrorAction SilentlyContinue
                }
            }
            $match = [regex]::Match($logText, 'https://[a-z0-9-]+\.trycloudflare\.com', 'IgnoreCase')
            if ($match.Success) {
                $tunnelUrl = $match.Value.TrimEnd('/')
                break
            }
            $tunnelProcess.Refresh()
            if ($tunnelProcess.HasExited) {
                if ($logText -match 'status 429|rate.?limit') {
                    if ($attempt -ge 2) {
                        throw "Cloudflare Quick Tunnel 当前触发 429 限流。请等待 5—10 分钟后重新双击启动，不要连续重复启动。"
                    }
                    break
                }
                $lastLine = ($logText -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -Last 1)
                throw "cloudflared 已退出：$lastLine。日志：$RunLogDir"
            }
            Start-Sleep -Milliseconds 700
        }
    }
    if (-not $tunnelUrl) {
        throw "75 秒内未获得临时 HTTPS 地址，请查看 cloudflared 日志。"
    }
    Set-Content -LiteralPath $UrlFile -Value $tunnelUrl -Encoding ASCII
    Save-State
    Write-Host "[OK] HTTPS 地址已生成：$tunnelUrl" -ForegroundColor Green

    Write-Host "[5/5] 启动 FastAPI，并绑定本次 HTTPS 来源..."
    $env:AI_POSE_URL = "http://127.0.0.1:8101"
    $env:ALLOWED_ORIGINS = $tunnelUrl
    $env:COOKIE_SECURE = "true"
    $env:ENABLE_DEMO_ACCOUNTS = "false"
    Start-TrackedProcess -Name "FastAPI" -FilePath $Python `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $BackendRoot -LogPrefix "backend" | Out-Null
    Wait-HttpReady -Name "FastAPI" -Url "http://127.0.0.1:8000/health" -TimeoutSeconds 60

    $publicReady = $false
    $publicDeadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $publicDeadline) {
        try {
            $health = Invoke-RestMethod -Uri "$tunnelUrl/api/health" -TimeoutSec 5
            if ($health.status -eq "ok") {
                $publicReady = $true
                break
            }
        }
        catch {
            $tunnelProcess.Refresh()
            if ($tunnelProcess.HasExited) { throw "隧道进程已退出。请查看 $RunLogDir" }
            $tunnelErrors = Get-Content -LiteralPath (Join-Path $RunLogDir 'cloudflared.err.log') -Tail 25 -ErrorAction SilentlyContinue
            if ($tunnelErrors -match 'Unauthorized: Tunnel not found') {
                throw "Cloudflare 已拒绝该临时隧道，请稍后重新启动。日志：$RunLogDir"
            }
            Start-Sleep -Seconds 2
        }
    }
    if (-not $publicReady) {
        throw "公网 /api/health 未通过验证；手机端尚不可用。请检查网络与日志：$RunLogDir"
    }

    Write-Host ""
    Write-Host "启动完成。" -ForegroundColor Green
    Write-Host "手机和电脑统一使用：$tunnelUrl" -ForegroundColor Cyan
    Write-Host "健康检查：$tunnelUrl/api/health"
    Write-Host "当前网址已保存到：$UrlFile"
    Write-Host "本次运行日志：$RunLogDir"
    Write-Host "停止服务：双击项目根目录的 关闭手机HTTPS.bat"
    Write-Host "提示：临时网址会在下次重新启动时变化；测试期间电脑不能休眠。"
}
catch {
    Write-Host "启动失败：$($_.Exception.Message)" -ForegroundColor Red
    Stop-StartedProcesses
    Remove-Item -LiteralPath $StateFile, $UrlFile -Force -ErrorAction SilentlyContinue
    throw
}
finally {
    try {
        Stop-Transcript | Out-Null
    }
    catch {
        # No transcript was active.
    }
}
