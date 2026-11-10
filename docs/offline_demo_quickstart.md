# 离线视频验证快速开始（RepCount + InfiniteRep）

## 1. 准备数据（首次或更新数据集后）

```bash
python scripts/setup_offline_demo.py
```

（等价于按需 `download_demo_datasets` + `download_infinite_rep` + `sync_demo_videos` + 校验）

- 数据在 `data/datasets/`（RepCount-A、InfiniteRep）
- 演示用副本与清单在 `data/demo_videos/manifest.json`

## 2. 启动服务

```bash
# 终端 1：后端
cd backend && uvicorn app.main:app --reload --port 8000

# 终端 2：前端
cd frontend && npm run dev
```

浏览器打开 `http://127.0.0.1:5173`，登录后进入 **运动中监测**。

首次使用请注册并完成首次测评。手动启动默认禁用演示账号；如需运行 `scripts/e2e_offline_demo.py`，请在后端启动前设置环境变量 `ENABLE_DEMO_ACCOUNTS=true`，或使用 README 的本地一键启动脚本。上传视频会按账号隔离，旧共享上传文件需重新上传，详见 [authentication.md](authentication.md)。

## 3. 跑通闭环

1. **输入** → 离线视频（推荐）
2. **演示样本** 下拉选一条（如 `[Rep] squat/repcount_stu4_66.mp4`），等待解析完成
3. 动作类型会自动匹配（深蹲 / 开合跳 / 俯卧撑等）
4. **开始会话** → **结束并生成报告** → 查看 CoT 报告页

也可用手动「选择文件」指向 `data/demo_videos/` 下任意 mp4。

**姿态模型**：当前演示为浏览器 **MediaPipe**（2D）。服务端 **RTMPose（COCO-17）** 代码已就绪，计划放到服务器再做离线精标演示，见 [rtmpose_server_plan.md](./rtmpose_server_plan.md)。

## 4. API（可选）

- `GET /demo-videos/manifest` — 演示列表
- `GET /demo-videos/file?rel=squat/repcount_stu4_66.mp4` — 拉取 mp4

## 5. 推荐演示组合

| 场景 | 样本 |
|------|------|
| 真实深蹲、多重复 | `squat/repcount_stu4_66.mp4` |
| 合成深蹲 | `squat/infinite_000000.mp4` |
| 开合跳 | `jump_jack/repcount_*.mp4` |
| 俯卧撑 | `push_up/repcount_*.mp4` |
