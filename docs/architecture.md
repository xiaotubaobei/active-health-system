# 主动健康智能服务系统 — 框架说明

版本：`0.1.0-framework`（导师要求的第一步：先搭框架）

## 技术栈

- 前端：Vue3 + Vite + Vue Router
- 后端：FastAPI + SQLAlchemy（默认 SQLite，可切 PostgreSQL）
- AI：独立 HTTP 服务桩（mock），后续替换为真模型
- 启动：`scripts/start_framework.ps1` 或分别启动

## 主闭环

1. 登录/档案 → 2. 体适能评估 → 3. 生成处方 → 4. 体型解析（可选）  
→ 5. 运动会话（姿态 mock）→ 6. 行为理解五任务 + Video CoT 报告 → 7. 处方版本+1

## AI 端口

| 服务 | 端口 |
|---|---|
| pose | 8101 |
| pose_kb | 8102 |
| video_gen | 8103 |
| parsing | 8104 |
| visual_encoder | 8105 |
| behavior | 8106 |
| video_cot | 8107 |
| backend API | 8000 |
| frontend | 5173 |
