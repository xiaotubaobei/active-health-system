# 核心 API（框架版）

## 本人训练反馈

`GET /sessions/{id}/feedback` 返回 `{feedback: null}` 或已保存的反馈。只允许当前登录用户访问本人已结束的训练；其他用户或不存在的训练返回404，未结束或已取消返回409。

`PUT /sessions/{id}/feedback` 全量保存本人填写的感受，必传非负整数 `expected_revision`（首次为0）和布尔值 `performed`。本人实际训练时，必须同时填写 `completion`（`completed|partial|stopped`）、`effort`（`easy|moderate|hard`）和布尔值 `discomfort`；仅体验样本时三项必须省略或为null。`note` 选填，最多1000字，保存时去除首尾空白。接口不接收目标用户编号，Cookie 写请求沿用登录接口的来源校验。

成功返回 `{feedback}`，含训练/用户编号、上述回答、`revision`、UTC 创建与修改时间。相同版本和内容的重复保存不增加版本；响应丢失后重试上一版本的相同内容也返回原结果。其他过期修改返回409，客户端保留本页内容，提示重新读取核对，不能自动覆盖。每条训练最多一份当前反馈，允许本人之后修改，不提供修改历史。反馈独立于模型评分、计数、知识库和处方，不自动参与统计或调整计划。启动迁移自动为已有安装创建 `session_feedback` 表。

## 训练草稿与恢复

`GET /sessions/{id}?user_id=本人ID` 返回训练和当前 `draft_revision`。

`PUT /sessions/{id}/draft?user_id=本人ID` 接收 `video_path`、`pose_summary` 和可选非负 `expected_revision`。新前端必须传入读取到的版本；保存成功返回新版本。状态不再是 running 或版本冲突返回409，不应盲目重传旧数据覆盖，应重新读取训练核对。

`POST /sessions/{id}/finish` 同样支持 `expected_revision`，归档时检查版本。已完成训练重复结束仍返回原报告；请求超时后可先查询状态，已完成则打开原报告。取消训练或结束训练后，草稿保存会被拒绝。

摄像头采样由前端产生 MediaPipe-33 与转换后的 COCO-17 序列，每10秒保存完整快照，单次最多1200帧。仅在实际检测到人体时产生帧；没有检测结果不会补造姿态、动作次数或有效评分。版本列由 SQLite 启动迁移补齐，旧记录从0开始。

## 登录与访问权限

注册密码为 8–128 字符，用户名为 2–64 字符；注册只能创建普通用户，`role=admin|physician|prescription_specialist` 返回 422。`demo`、`specialist`、`physician`、`admin` 为保留名称。演示账号默认关闭，仅显式设置 `ENABLE_DEMO_ACCOUNTS=true` 后允许 `demo / 123456` 登录，权限仍是普通用户。

登录和注册返回 `{token, user}`，同时设置 8 小时有效的 HttpOnly、SameSite=Lax Cookie。前端使用 Cookie；命令行可使用 `Authorization: Bearer <token>`。服务器只保存凭证摘要；退出后当前凭证失效。Cookie 方式的写入请求必须带 `X-Requested-With: ActiveHealth`，跨域请求的 Origin 必须在 `ALLOWED_ORIGINS` 中。不要将 token 放入 URL 或日志。

个人档案、首次测评、体测、体型解析、处方、训练、报告、设备、知识库及姿态推理均需登录。`user_id` 为兼容现有客户端保留，必须等于服务器识别的当前账号；它本身不能作为登录凭证。访问其他用户或其记录统一返回 404，缺少、伪造或过期凭证返回 401。目录类接口（量表、处方模板与状态流、公共演示视频）及 `/health` 公开。

普通用户不能直接推进处方状态（403），修改本地缓存或提交 `role` 不能提权。跨用户审核只开放用户明确提交给指定人的资料快照，不开放其他个人接口。配置、迁移和验收详见 [authentication.md](authentication.md) 和 [prescription_review.md](prescription_review.md)。

## 业务

- `GET /health`
- `POST /auth/login` `{username, password}`
- `POST /auth/register` `{username, password, privacy_consent: true}`
- `POST /auth/logout` 撤销当前登录凭证并清除 Cookie
- `GET /onboarding/status?user_id=`
- `POST /onboarding/complete` 保存档案、首次测评基线及初始模板处方
- `GET /users/me`
- `PUT /users/me`
- `GET /fitness/scales`
- `POST /fitness/assess`
- `POST /body/parse`
- `GET /prescriptions/templates`
- `POST /prescriptions/generate`
- `GET /prescriptions/current?user_id=`
- `POST /prescriptions/{id}/advance` 已停用，需走人工审核；本人普通账号403，有角色的本人409，其他人404
- `POST /prescriptions/{id}/reviews` 提交审核
- `GET /prescriptions/reviews/mine?offset=0&limit=50` 本人的送审记录
- `GET /prescriptions/reviews/inbox?status=pending&offset=0&limit=50` 指定给当前审核人的记录
- `POST /prescriptions/reviews/{id}/cancel` 本人撤回待审申请
- `POST /prescriptions/reviews/{id}/decision` 指定审核人写入决定
- `POST /sessions/start`
- `GET /sessions/{id}?user_id=` 获取原训练及已保存的输入
- `PUT /sessions/{id}/draft?user_id=` 保存未完成训练的姿态与视频引用
- `POST /sessions/{id}/cancel?user_id=` 取消未完成训练
- `POST /sessions/{id}/finish`
- `GET /reports/{session_id}`
- `GET /users/{user_id}/sessions?limit=50` 最近训练（最多 200 条）
- `GET /users/{user_id}/sessions/page?page=1&page_size=10&status=&exercise_id=` 分页及筛选训练
- `GET /users/{user_id}/kb/summary?limit=20` 个人知识库摘要（最多 100 条的统计窗口）
- `GET /users/{user_id}/kb/entries?limit=50` 归档明细（最多 200 条）
- `POST /demo/run-loop` `{user_id}` 演示训练归档，不写入假体测、不调整处方
- `POST /devices/readings`

## 人工审核接口

送审请求为 `{reviewer_username, consent: true, request_note: "选填"}`。仅本人当前版 `pre_prescription|monitoring` 可送审；同版只允许一个待审申请。医疗模板需指定 `physician`，健身模板允许 `physician|prescription_specialist`，禁止自审。缺少明确同意或审核账号不可用返回400；重复送审、旧版或已正式通过返回409。

`mine` 与 `inbox` 返回 `{total, items}`，`offset >= 0`、`limit` 为1–100。`mine` 包括本人全部申请状态；`inbox` 仅限当前仍具资格的指定审核人，`status` 可为 `pending|approved|rejected`，普通账号403。撤回或新版失效的申请不对审核人开放。

审核决定为 `{decision: "approved"|"rejected", note: "必填意见"}`，意见去除空白后必须非空且最多2000字。通过只将原版标记为正式处方，退回不改原版。记录包含申请编号、双方编号和账号名、角色、状态、处方快照、档案/最近测评快照、提交说明、决定意见及UTC时间。已处理记录不能覆盖；用户可撤回待审申请，退回后可创建独立新申请。新版生成在同一事务内将旧待审记录标记为 `superseded`。

## 首次测评与分数校验

新账号在首次测评完成前不能开始训练。`/onboarding/complete` 接收 `user_id`、`age_group`（`youth|middle_age|elder`）、`height_cm`、`weight_kg`、`goal`（`fitness|medical`）、`chronic_tags`、`scale_id`、`scores`、`privacy_consent: true`，默认生成初始模板处方。

量表从 `/fitness/scales` 获取：青少年用 `youth`，其他年龄组用 `middle_elder`。`scores` 必须提供当前量表的全部项目，每项为 0–100 的换算分；缺项、额外项目、越界、未知量表均返回 422，不保存不完整评估。重复完成首次测评返回 409；后续测评使用 `/fitness/assess`。

## 训练恢复、取消与历史筛选

`POST /sessions/start` 除用户、动作与处方编号外，可接收 `video_path` 和 `pose_summary`，随训练一起保存。`GET /sessions/{id}?user_id=` 返回 `{session}`，包含已保存的输入，供页面刷新后恢复。前端 URL 保留训练编号，历史页也提供未完成训练入口。

`PUT /sessions/{id}/draft?user_id=` 接收完整的 `{video_path, pose_summary}`，替换未完成训练的输入；已完成或取消返回 409。前端在训练中重新解析视频成功后保存该输入。恢复的是已保存的姿态与视频引用；本地文件预览和摄像头需用户重新选择或打开，尚未结束时的摄像头实时帧不持续保存。

`POST /sessions/{id}/cancel?user_id=` 将未完成训练改为 `cancelled`，不生成报告或知识库归档；重复取消返回原记录，已完成返回 409。详情、保存、取消与结束均由后端检查当前登录账号及记录归属；其他用户即使传入自己的 `user_id`，也无法访问该训练。

分页历史返回 `{items, total, page, page_size, exercises}`。`page >= 1`，`page_size` 为 1–100；`status` 可选空字符串、`running`、`finished`、`cancelled`，`exercise_id` 精确匹配。记录按编号倒序；每项含 `analysis`（未归档时为 `null`）及 `history_note`，旧记录也可独立查看评估摘要。`exercises` 为该用户所有动作选项，不受本次筛选影响。页码超出范围返回空 `items`。原有列表接口不变，知识库顶部均分仍按最近归档窗口统计，不跟随历史筛选。

## 训练结束与评估状态

`POST /sessions/{id}/finish` 接收 `video_path` 和 `pose_summary`，返回 `session`、`report`、`kb_entry_id`、`analysis`、`updated_prescription`。报告和知识库原子保存，失败回滚后可重试；重复请求返回原报告，不覆盖首次保存的视频与姿态。旧报告若原来没有知识库条目，重复结束仍返回原报告，不自动补写历史数据。

结束时未提供视频或姿态则使用训练内已保存的值；没有视频引用时保留空字符串，不补造视频文件路径。取消后的训练不能结束，返回 409。

`analysis` 示例：

```json
{"status": "demo", "mode": "local_fallback", "score": null, "message": "当前为演示或未完成评估，不计入成绩，也不自动调整处方"}
```

- `status=model`：服务明确返回 `mode=remote|model`、有效 0–100 分且没有失败标记；0 分是有效值。
- `status=demo`：`mock|local_fallback`；`score=null`。
- `status=unavailable`：结果不完整、失败或来源未标记；`score=null`。
- `updated_prescription` 当前固定为 `null`；真实模型结果也保留待审核，不自动调整处方。
- `/reports/{session_id}` 同样返回 `analysis`；原始 `report.cot` 保留用于调试，可能含演示分数，界面与统计以 `analysis` 为准。

知识库 `kb_entries` 为全部归档条数；`avg_score_recent` 只统计最近 `limit` 条中的有效模型评估，无有效值返回 `null`，有效条数见 `scored_entries_recent`。历史未标记来源的结果不计入成绩。

姿态中的 `motion_analysis` 会原样保存到报告及知识库姿态摘要，当前未实现动作计数算法。报告支持的预留格式为：`status=ok`、`rep_count`、`rep_intervals=[{start_sec, end_sec}]`；失败时 `status=failed`、`rep_count=null`、`error` 为原因。没有结果时不补造次数。

## 视频引用与上传

`POST /pose/infer-video-upload` 需要登录，接收 `file`、`sample_hz`（1–15）及可选 `exercise_id`。支持 mp4、mov、avi、webm、mkv，单文件最多 100 MB。文件存入 `uploads/offline/<当前用户编号>/<随机名称>.<后缀>`，成功后返回 `upload_rel`，同名上传互不覆盖。

`POST /pose/infer-video`、训练开始 / 保存 / 结束及体型解析的非空媒体路径，只允许公共 `data/demo_videos/` 或当前用户的上传目录。公共视频也兼容 `demo_videos/...` 别名；路径越界返回 404，包含 `..` 返回 400。旧版共享 `uploads/offline/<文件名>` 无法证明归属，需用户重新上传；已有完成报告仍可回看，重复结束仍返回原报告。浏览器本地分析未上传的视频只保存姿态，不伪造服务器路径。

## AI 契约示例

### `POST /evaluate` (video_cot:8107)

```json
{
  "video_path": "...",
  "exercise_name": "深蹲",
  "pose_summary": {},
  "parsing_summary": {}
}
```

返回：`steps[]`, `score`, `errors[]`, `advice`, `raw_cot`

### `POST /infer` (behavior:8106)

`task`: `recognize|localize|segment|assess|describe`
