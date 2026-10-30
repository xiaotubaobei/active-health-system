# 主动健康智能服务系统（初版演示）

对齐国自然申请书《面向主动健康的高性能人体运动感知与理解技术》。当前版本：`0.2.0-demo`（可给导师演示的初版）。

导师演示说明见 [docs/advisor_v1.md](docs/advisor_v1.md)。

## 快速启动（Windows）

```powershell
cd C:\Users\DELL\Desktop\liudawei\active-health-system
powershell -ExecutionPolicy Bypass -File .\scripts\start_framework.ps1
```

或手动：

```powershell
# 1) AI 桩
python scripts\run_ai_stubs.py

# 2) 后端
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# 3) 前端
cd ..\frontend
npm install
npm run dev
```

- 前端：http://127.0.0.1:5173  
- API 文档：http://127.0.0.1:8000/docs  
- 演示账号：`demo` / 密码 `123456`

## 假数据闭环演示路径

最快：登录后在总览点 **「一键跑通演示闭环」**。

手动：

1. 登录 → 档案（`demo` / `123456`）  
2. 体适能评估（需自己填分）  
3. 生成处方  
4. 运动中：打开摄像头（可见骨架）→ 开始会话 → 结束会话  
5. 报告页查看 CoT；处方版本自动 +1  

也可命令行冒烟：

```powershell
python scripts\smoke_test.py
```

## 离线视频验证（RepCount + InfiniteRep，无需摄像头）

首次或更新数据集后：

```powershell
python scripts\setup_offline_demo.py
```

启动前后端后，登录 **运动中监测** → **离线视频** → **演示样本** → 解析 → **开始会话** → **结束并生成报告**。  
详见 [docs/offline_demo_quickstart.md](docs/offline_demo_quickstart.md)。后端已启动时可跑 API 冒烟：`python scripts/e2e_offline_demo.py`。

## 文档

- [docs/module_map.md](docs/module_map.md) 申请书条款对照  
- [docs/architecture.md](docs/architecture.md) 架构  
- [docs/api.md](docs/api.md) API  
- [docs/schemas.md](docs/schemas.md) CoT / 五任务 / 处方 Schema  

后续再把各 AI 桩替换为真模型（姿态 / 解析 / Video-R2 CoT 等）。
