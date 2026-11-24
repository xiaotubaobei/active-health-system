# 主动健康智能服务系统（初版演示）

对齐国自然申请书《面向主动健康的高性能人体运动感知与理解技术》。当前版本：`0.2.0-demo`（可给导师演示的初版）。

导师演示说明见 [docs/advisor_v1.md](docs/advisor_v1.md)。

两位实习生分别使用 `a`、`b` 分支，具体任务、文件归属、首周验收与手机端路线见 [docs/intern_tasks_and_mobile_plan.md](docs/intern_tasks_and_mobile_plan.md)。本轮交接统一包含处方人工审核功能。

手机试用的 HTTPS 部署配置、数据保留、备份和验收步骤见 [docs/mobile_deployment.md](docs/mobile_deployment.md)。服务器部署与真机验收尚未完成。

本轮进展与验收步骤见 [docs/progress_20261110.md](docs/progress_20261110.md)：已接通注册、首次测评、训练归档、报告回看、未完成训练恢复与取消、历史分页和筛选；后端验证登录身份，个人数据和上传视频按账号隔离。演示分数不参与成绩统计，训练结束不自动修改处方。

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
- 首次使用请注册个人账号，用户名 2–64 字符，密码 8–128 字符。
- 一键启动脚本显式开启本地演示账号 `demo` / `123456`；手动启动默认关闭。需要演示时，在启动后端的 PowerShell 中先设置 `$env:ENABLE_DEMO_ACCOUNTS="true"`。演示账号只有普通用户权限，旧的默认医师、专家、管理员账号禁止登录。
- 后端启动时自动创建表，并为旧 SQLite 数据库补齐已知缺列；旧明文密码转为加盐哈希，原密码仍可登录，保留现有业务数据。旧浏览器登录需重新登录一次。
- 登录有效期为 8 小时，退出立即撤销当前凭证。账号与部署配置见 [docs/authentication.md](docs/authentication.md)。

## 假数据闭环演示路径

最快：登录后在总览点 **「一键跑通演示闭环」**。

手动：

1. 登录页切换「注册新用户」，设置账号与密码，勾选同意。
2. 在「首次测评」填写资料和当前量表的全部项目分数（0–100 的换算分，不是原始 BMI、次数或秒数），提交后保存基线并生成初始模板处方。
3. 在总览点「一键跑通演示闭环」，或去运动页完成一次会话；演示账号可直接登录体验。
4. 报告页查看姿态摘要和评估状态。演示 / 服务备用结果显示「暂无有效评分」，真实模型评估才展示有效分数。动作计数未接入时显示暂无结果。
5. 打开「训练历史与知识库」回看本次报告；同一训练重复结束只保存一次。处方不会因训练完成而自动增加版本。
6. 未完成训练可从历史页点「继续本次训练」，刷新也可恢复原编号及已保存的姿态数据；不需要保留的训练可取消。历史可按状态、动作筛选并翻页。窄屏下点「展开导航」切换页面。

也可命令行冒烟：

```powershell
python scripts\smoke_test.py
```

脚本会新建一个独立测试账号并写入一条训练记录，不修改演示账号。可不启动 AI 服务；它验证业务链路，不证明真实算法效果。

## 处方人工审核

训练计划中的动作可点击“练这个动作”进入训练页，查看目标组数、次数和计划版本。开始训练时由后端校验动作并保存计划快照，恢复训练仍使用原目标；目标不代表实际完成量。旧训练没有快照时不会补造目标。现阶段一次训练对应一个动作，尚不自动推进整套计划。

用户在「运动处方」填写指定审核人账号、同意共享本次资料快照后送审。审核人在「处方人工审核」填写意见并通过或退回；双方可回看记录。生成新版自动使旧待审申请失效。审核账号需由本机维护工具为已注册个人账号设置角色，具体命令和验收步骤见 [docs/prescription_review.md](docs/prescription_review.md)。

## 开发检查

摄像头训练现已采集实际 MediaPipe 姿态帧（每秒最多2帧），每10秒自动保存到服务端，并提供立即保存、失败重试、最近保存时间和离开提醒。恢复后沿用已保存的帧，最多1200帧；达到上限需结束本次训练。只保存姿态，不录制或上传摄像头原视频。断网和关闭页面前尚未成功保存的数据仍可能丢失；不支持离线训练同步。

保存使用版本检查，其他页面更新后会停止覆盖并提示核对。结束训练先保存输入；响应丢失时检查已生成报告。开始请求响应丢失后，当前页重试或同一标签页刷新都会先找回原训练，避免重复建立记录；未查到时沿用原请求编号重试，网络异常时暂停新建。浏览器只暂存请求编号、动作、计划编号和输入方式，不暂存视频或姿态帧。关闭标签页或清除浏览器数据后，请从训练历史找回；尚未保存的采集数据无法靠此功能恢复。更新后需重启后端以补齐 SQLite 的保存版本列、开始请求编号及唯一索引。

摄像头训练支持暂停、继续和采集计时，暂停时关闭摄像头，暂停及模型加载时间不计入。切到后台自动暂停，回来需手动继续；恢复训练沿用已保存计时，满1200帧自动暂停。计时不代表动作完成量。推荐样本按当前动作选择，无匹配样本时按钮不可用。

模型与 WASM 改由本站提供。`npm run dev` 和 `npm run build` 会先准备并校验官方模型；首次构建需下载，后续复用正确文件。无法下载时的本地文件准备方法及 `--camera-assets` 部署检查见 [手机部署说明](docs/mobile_deployment.md)。真实手机、HTTPS 和网络兼容仍需部署后单独验收。

摄像头现支持取消加载，离开页面后会释放晚到的权限请求；修正骨架重复镜像，模型下载失败后可关闭重开摄像头重试。

训练保存与摄像头生命周期检查：`node --test frontend/tests/*.test.mjs`（替代网络和摄像头边界，不代表真机验收）。

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

标准部署默认在浏览器解析本地视频，不需要另启 RTMPose；上限100MB、3分钟，解析中可取消。建议先用10～30秒的MP4全身动作片段。本地开发可在 `frontend/.env` 设置 `VITE_POSE_OFFLINE=browser`，重启前端后生效；保留 `server` 则需单独启动 RTMPose。

首次或更新数据集后：

```powershell
python scripts\setup_offline_demo.py
```

启动前后端后，登录 **运动中监测** → **离线视频** → **演示样本** → 解析 → **开始会话** → **结束并生成报告**。  
详见 [docs/offline_demo_quickstart.md](docs/offline_demo_quickstart.md)。后端开启本地演示账号后，可跑 API 冒烟：`python scripts/e2e_offline_demo.py`。该脚本使用 mock 姿态，不验证真实算法。

## 文档

- [用户流程实测与下一步](docs/user_journey_20261124.md)：2026-11-24 的完整流程、已修问题与剩余验收项。
- [docs/module_map.md](docs/module_map.md) 申请书条款对照  
- [docs/architecture.md](docs/architecture.md) 架构  
- [docs/api.md](docs/api.md) API  
- [docs/schemas.md](docs/schemas.md) CoT / 五任务 / 处方 Schema  

后续再把各 AI 桩替换为真模型（姿态 / 解析 / Video-R2 CoT 等）。
