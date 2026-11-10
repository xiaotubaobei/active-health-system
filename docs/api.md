# 核心 API（框架版）

## 业务

- `GET /health`
- `POST /auth/login` `{username, password}`
- `POST /auth/register` `{username, password, privacy_consent: true}`
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
- `POST /prescriptions/{id}/advance` 推进状态机
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

## 首次测评与分数校验

新账号在首次测评完成前不能开始训练。`/onboarding/complete` 接收 `user_id`、`age_group`（`youth|middle_age|elder`）、`height_cm`、`weight_kg`、`goal`（`fitness|medical`）、`chronic_tags`、`scale_id`、`scores`、`privacy_consent: true`，默认生成初始模板处方。

量表从 `/fitness/scales` 获取：青少年用 `youth`，其他年龄组用 `middle_elder`。`scores` 必须提供当前量表的全部项目，每项为 0–100 的换算分；缺项、额外项目、越界、未知量表均返回 422，不保存不完整评估。重复完成首次测评返回 409；后续测评使用 `/fitness/assess`。

## 训练恢复、取消与历史筛选

`POST /sessions/start` 除用户、动作与处方编号外，可接收 `video_path` 和 `pose_summary`，随训练一起保存。`GET /sessions/{id}?user_id=` 返回 `{session}`，包含已保存的输入，供页面刷新后恢复。前端 URL 保留训练编号，历史页也提供未完成训练入口。

`PUT /sessions/{id}/draft?user_id=` 接收完整的 `{video_path, pose_summary}`，替换未完成训练的输入；已完成或取消返回 409。前端在训练中重新解析视频成功后保存该输入。恢复的是已保存的姿态与视频引用；本地文件预览和摄像头需用户重新选择或打开，尚未结束时的摄像头实时帧不持续保存。

`POST /sessions/{id}/cancel?user_id=` 将未完成训练改为 `cancelled`，不生成报告或知识库归档；重复取消返回原记录，已完成返回 409。上述详情、保存与取消接口校验记录与传入 `user_id` 是否一致，不一致返回 404；这仍不能替代正式身份鉴权。

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

知识库 `kb_entries` 为全部归档条数；`avg_score_recent` 只统计最近 `limit` 条中的有效模型评估，无有效值返回 `null`，有效条数见 `scored_entries_recent`。历史未标记来源的结果不计入成绩。接口目前沿用本地演示的开发登录和 `user_id` 参数，尚未实现正式服务端身份鉴权。

姿态中的 `motion_analysis` 会原样保存到报告及知识库姿态摘要，当前未实现动作计数算法。报告支持的预留格式为：`status=ok`、`rep_count`、`rep_intervals=[{start_sec, end_sec}]`；失败时 `status=failed`、`rep_count=null`、`error` 为原因。没有结果时不补造次数。

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
