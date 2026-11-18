# 申请书条款 → 代码路径对照

| 申请书 | 代码位置 |
|---|---|
| 图14 智能服务系统 / 运动前中后 | `frontend/src/views/*` + `backend/app/routers/*` |
| 2.1.1 姿态辅助视频生成 | `ai_services/video_gen` |
| 2.1.1 姿态估计 | `ai_services/pose` |
| 2.1.1 姿态知识库与序列优化 | `ai_services/pose_kb` |
| 2.1.2 开集人体解析 | `ai_services/parsing` |
| 2.1.2 交互点击辅助 | `frontend/src/views/BodyParse.vue` |
| 2.1.3 视觉句子 / 混合编码器 | `ai_services/visual_encoder` |
| 2.1.3 查询式五任务行为理解 | `ai_services/behavior` |
| 2.1.3 评估+描述（Video CoT） | `ai_services/video_cot` |
| 2.1.4 体适能量表 表8/9 | `data/fitness_scales/` |
| 2.1.4 健身/医疗处方 表10/11 | `data/prescription_templates/` |
| 图15 处方状态机 | `backend/app/services/prescription.py` |
| 手环/设备接入 | `backend/app/routers/devices.py` |
| 处方师/医师角色与人工审核 | `User.role` + `scripts/set_user_role.py` + `backend/app/routers/prescriptions.py` + `frontend/src/views/Reviews.vue` |

## 处方状态机（对齐图15）

`clinical_intake` → `fitness_assessed` → `pre_prescription` → `monitoring` → `formal_prescription` → `implementing` → `feedback` →（可回写微调新版本）

上行为申请书目标流程。当前实现支持模板预处方送审、人工通过后标记正式处方；训练与演示不自动推进其余阶段或回写微调。已实现的审核范围、角色开通和验收步骤见 [prescription_review.md](prescription_review.md)。
