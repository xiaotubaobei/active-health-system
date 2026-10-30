# 仅启动本地 RTMPose 姿态服务（8101）
$Root = Split-Path $PSScriptRoot -Parent
$Pose = Join-Path $Root "ai_services\pose"
Write-Host "启动 RTMPose @ http://127.0.0.1:8101"
Write-Host "  MODE=$env:RTMPOSE_MODE BACKEND=$env:RTMPOSE_BACKEND DEVICE=$env:RTMPOSE_DEVICE"
if (-not $env:RTMPOSE_MODE) { $env:RTMPOSE_MODE = "balanced" }
if (-not $env:RTMPOSE_BACKEND) { $env:RTMPOSE_BACKEND = "onnxruntime" }
if (-not $env:RTMPOSE_DEVICE) { $env:RTMPOSE_DEVICE = "cpu" }
Set-Location $Pose
pip install -r requirements.txt -q
python main.py
