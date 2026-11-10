# 主动健康智能服务系统（初版演示）

对齐国自然申请书《面向主动健康的高性能人体运动感知与理解技术》。当前版本：`0.2.0-demo`（可给导师演示的初版）。

导师演示说明见 [docs/advisor_v1.md](docs/advisor_v1.md)。

本轮进展与验收步骤见 [docs/progress_20261110.md](docs/progress_20261110.md)：已接通注册、首次测评、训练归档、报告回看与历史记录；演示分数不参与成绩统计，训练结束不自动修改处方。

## 快速启动（Windows）

```powershell
cd C:\Users\DELL\Desktop\liudawei\active-health-system
powershell -ExecutionPolicy Bypass -File .\scripts\start_framework.ps1
```

或手动：

```powershell
# 1) AI 桩（可选；未启动时后端使用明确标记的备用结果）
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
- 后端启动时自动创建表，并为旧 SQLite 数据库补齐已知缺列；保留现有数据。

## 假数据闭环演示路径

最快：登录后在总览点 **「一键跑通演示闭环」**。

手动：

1. 登录页切换「注册新用户」，设置账号与密码，勾选同意。
2. 在「首次测评」填写资料和当前量表的全部项目分数（0–100 的换算分，不是原始 BMI、次数或秒数），提交后保存基线并生成初始模板处方。
3. 在总览点「一键跑通演示闭环」，或去运动页完成一次会话；演示账号可直接登录体验。
4. 报告页查看姿态摘要和评估状态。演示 / 服务备用结果显示「暂无有效评分」，真实模型评估才展示有效分数。动作计数未接入时显示暂无结果。
5. 打开「训练历史与知识库」回看本次报告；同一训练重复结束只保存一次。处方不会因训练完成而自动增加版本。

也可命令行冒烟：

```powershell
python scripts\smoke_test.py
```

脚本会新建一个独立测试账号并写入一条训练记录，不修改演示账号。可不启动 AI 服务；它验证业务链路，不证明真实算法效果。

## 开发检查

在项目根目录运行后端检查（测试使用临时数据库，不修改现有库）：

```powershell
python -m pip install -r backend\requirements-dev.txt
python -m pytest backend\tests -q
```

前端构建：

```powershell
cd frontend
npm run build
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
