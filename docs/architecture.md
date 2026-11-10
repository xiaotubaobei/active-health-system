# 主动健康智能服务系统 — 框架说明

版本：`0.1.0-framework`（导师要求的第一步：先搭框架）

## 技术栈

- 前端：Vue3 + Vite + Vue Router
- 后端：FastAPI + SQLAlchemy（默认 SQLite，可切 PostgreSQL）
- AI：独立 HTTP 服务桩（mock），后续替换为真模型
- 启动：`scripts/start_framework.ps1` 或分别启动

## 主闭环

1. 登录/档案 → 2. 体适能评估 → 3. 生成处方 → 4. 体型解析（可选）  
→ 5. 运动会话 → 6. 保存报告与个人知识库 → 7. 训练历史回看

2026-11-10 更新：新账号先完成首次测评与初始模板处方。后端启动时执行轻量迁移；结束训练共用一个归档入口，报告与知识库在同一事务内保存，重复结束复用首次结果。演示 / 备用评分不计入模型成绩；训练结束不自动调整处方。真实姿态需配置 RTMPose 服务，当前行为理解 / CoT 仍可使用服务桩。

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
