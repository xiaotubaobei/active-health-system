# RTMPose 服务端（后续上服务器演示）

当前阶段：**本地演示仍用浏览器 MediaPipe**（实时 + 离线 `demo_videos`）。  
服务器阶段：**离线精标 / 答辩强调精度** 时启用本服务。

## 已有代码

| 路径 | 说明 |
|------|------|
| `ai_services/pose/main.py` | `POST /infer/video`，`GET /estimator` |
| `ai_services/pose/rtmpose_runner.py` | rtmlib → **COCO-17**，按 `sample_hz` 抽帧 |
| `backend/app/services/ai_client.py` | `pose_infer_video()` 已封装 |

## 上服务器时启动

```bash
cd ai_services/pose
pip install -r requirements.txt
# 可选：RTMPOSE_MODE=performance RTMPOSE_DEVICE=cuda RTMPOSE_BACKEND=onnxruntime
python main.py   # 默认 0.0.0.0:8101
```

后端环境变量：`AI_POSE_URL=http://<服务器>:8101`

## 视频路径约定

`/infer/video` 的 `video_path` 必须是 **pose 进程能读到的本地路径**（与后端 `DATA_DIR` 下 `demo_videos/...` 或挂载卷一致）。

## 与前端的关系（尚未默认开启）

- **现在**：运动页离线模式 → 浏览器 MediaPipe → `finish` 提交 `pose_summary`  
- **后续**：离线 `finish` 前调用 `pose_infer_video`，用返回的 `coco17_frames` 填 `sequences.coco17`，`estimator` 改为 `rtmpose_*`；摄像头仍可只用 MediaPipe  

## 模式说明

`RTMPOSE_MODE`：`lightweight` | `balanced`（默认）| `performance`  
对应 RTMPose 小/中/大档，GPU 上优先 `performance`。
