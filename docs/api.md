# 核心 API（框架版）

## 业务

- `GET /health`
- `POST /auth/login` `{username, password}`
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
- `POST /sessions/{id}/finish`
- `GET /reports/{session_id}`
- `POST /devices/readings`

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
