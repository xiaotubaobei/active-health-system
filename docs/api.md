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

### 修改密码与尝试限制

`POST /auth/change-password` 需登录，请求为 `{current_password, new_password}`，不接受目标用户编号。当前密码最长128字符；新密码8–128字符，不能与当前密码相同，保留首尾空格。演示账号不支持修改。

成功返回 `{ok: true, reauthenticate: true}`，在同一事务中更新密码并撤销本人全部设备的登录凭证，再清除当前 Cookie。训练等业务记录保留。客户端收到成功后必须返回登录页，不继续使用旧 token。

当前密码错误或新旧密码相同返回400，登录仍有效；未登录或凭证过期401，演示账号/来源检查拒绝403，另一请求先改密409，字段格式错误422。`/auth/*` 的422响应不回传原始输入，避免包含密码。改密请求没有自动重试：响应丢失、5xx或409时返回登录确认，先尝试新密码，不成功再尝试原密码。

登录和改密分别使用60秒窗口的数据库额度：同一来源及账号组合5次、同一账号跨来源20次、同一来源跨账号60次。正确密码只清除组合额度；两个总额度保留到窗口结束。超限返回429及秒数形式 `Retry-After`，客户端等待后再试，不退出当前有效登录。来源由服务器识别的连接地址决定，不在应用内读取任意 `X-Forwarded-For`。可信代理配置与限制见账号说明。

## 业务

- `GET /health`
- `POST /auth/login` `{username, password}`
- `POST /auth/register` `{username, password, privacy_consent: true}`
- `POST /auth/logout` 撤销当前登录凭证并清除 Cookie
- `POST /auth/change-password` `{current_password, new_password}`，成功后所有设备重新登录
- `GET /onboarding/status?user_id=`
- `POST /onboarding/complete` 保存基本档案，可选一并录入完整体测和生成模板草案
- `GET /users/me`
- `PUT /users/me`
- `GET /fitness/scales`
- `POST /fitness/assess`
- `POST /body/parse`
- `GET /prescriptions/templates`
- `POST /prescriptions/generate`
- `GET /prescriptions/availability?user_id=` 只读查询当前档案是否有目录匹配模板及原因
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

## 基本建档与可选体测

新账号须先填写基本档案，再使用训练记录工具；不强制先完成体测，能记录训练不代表获得了运动适宜性确认。`/onboarding/complete` 接收 `user_id`、`age_group`（`youth|middle_age|elder`）、`height_cm`、`weight_kg`、`goal`（`fitness|medical`）、`chronic_tags`、`privacy_consent: true`。没有完整体测分数时不提供 `scale_id`、`scores`，接口仅建档，返回 `baseline: null`，不创建空评估或0分基线。

`generate_prescription` 为兼容旧客户端仍默认 `true`；新页面明确传 `false`，保存后展示建档结果，由用户另到方案页查看匹配并主动生成。旧客户端请求生成但无匹配时，档案及有效体测仍保存成功，返回 `prescription: null` 与 `prescription_message` 原因；不会用其他模板凑方案。`onboarding_done` 表示基本建档完成，与 `has_baseline`、`has_prescription` 独立。建档成功不自动跳转到计划页，不把未录体测的用户写成“首次测评已完成”。

`age_group`、`height_cm`、`weight_kg`、`goal` 必须明确提交，缺少任意一项返回422，不采用注册时的历史占位值。首次填写页面不预填年龄组、身高体重或目标。身高体重必须有限且大于0，上限分别为300厘米和700公斤；这些只是输入有效性边界，不是健康范围。旧库注册占位值及旧记录不在本次更新中猜测性改写。

选择同时录体测时，量表从 `/fitness/scales` 获取：青少年用 `youth`，其他年龄组用 `middle_elder`。`scores` 必须提供当前量表的全部项目，每项为 0–100 的换算分；缺项、额外项目、越界、未知量表、年龄不匹配均返回422，整个建档请求不写入。只提交量表、只提交分数，或没有体测却提交非空 `pose_baseline` 也拒绝，不静默丢弃数据。

重复建档返回409；补录及后续测评使用 `/fitness/assess`，同样校验档案年龄组，未基本建档不能录入。第一次有效录入创建首次基线，后续录入创建独立评估，保留原基线和当时的身高、体重等档案快照。记录基线与测评共用用户事务锁，防止并发录入创建重复首条基线。`GET /onboarding/status` 可区分仅建档、已有体测、已有方案。

现有项目和权重来自申请书骨架，尚无经核验的原始成绩换算标准。接口中的 `level` 仍保留旧版实验分档以兼容已有数据，不是已验证的健康等级；页面不再据此显示“达标”或建议进阶。`created_at` 是录入时间，尚无实际测量时间或测量来源字段。没有换算成绩时先建档即可，不能以估填分数代替真实测评。

模板选择仍只使用年龄组、目标和标签，不使用测评分数、身高体重或训练反馈。新生成的 `health_plan` 四项均为空，表示未评估；前端不能将空值解释成“没有问题”。旧版模板里的饮食、睡眠文本保留原记录，页面提示其模板来源。详细字段审查及后续改造要求见 [progress_20261125.md](progress_20261125.md#补充审查字段和建议是否对应真实用户)。

### 模板覆盖不足的处理

`/prescriptions/availability` 返回 `{matched, reason, library, template_id}`，只判断目录是否唯一匹配，不写记录，也不表示医学适用性。未建档时 `matched: false`，生成接口返回409，避免使用注册占位值。年龄必须一致；健身库同时要求目标一致；有健康标签或目标为健康管理时进入医疗模板库，必须提供非空标签集合，并与模板标签集合完全一致。当前没有多病种合并规则，仅一个标签重合不够，不对未知中文/英文标签自动推断或替换。

没有唯一匹配时 `POST /prescriptions/generate` 返回422，保留已有版本和待审记录，不递增版本或使旧申请失效；演示入口创建初始模板时也返回明确错误，不绕过匹配。页面展示原因，禁用生成，提供核对资料的入口；没有模板时专业人员从零建方案的功能仍待补充，不应伪装为已能送审。匹配成功的仍是模板草案，其强度、频次及进阶未经个人情况适配。仅在成功保存新版时按既有规则使旧待审申请失效。

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
