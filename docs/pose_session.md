# 运动会话姿态数据契约（`pose_summary`）

对齐申请书 **图3 人体运动分析**（估计 → 序列优化/知识库）与系统字段 `ExerciseSession.pose_summary`。

## 设计原则

| 原则 | 说明 |
|------|------|
| **双格式存储** | 保留采集端原始 **MediaPipe-33**；业务/KB/CoT 以 **COCO-17** 为主 |
| **主格式** | `canonical_format = "coco17"`，优化与检索默认读 `sequences.coco17` |
| **可追溯** | 记录 `converter_version`、估计器、精炼器版本 |
| **raw / optimized** | 估计器直出为 `raw`；经 KB/滤波/网络后为 `optimized` |

---

## 顶层结构 `pose_summary`

```json
{
  "schema_version": "1.0.0",
  "session_id": 9,
  "exercise_id": "squat",
  "exercise_name": "深蹲",

  "canonical_format": "coco17",
  "capture_format": "mediapipe33",
  "converter_version": "mp33_to_coco17_v1",

  "estimator": {
    "name": "mediapipe_pose_landmarker_lite",
    "runtime": "browser",
    "fps_sample": 8
  },
  "refiner": {
    "name": "pose_kb_v1",
    "mode": "mock|sg|smoothnet|pose_kb_attn"
  },

  "frame_meta": {
    "width": 640,
    "height": 480,
    "coord_space": "normalized_0_1"
  },

  "sequences": {
    "mediapipe33": { "frames": [] },
    "coco17": { "frames": [] }
  },

  "angles": {
    "per_frame": [],
    "summary": {
      "knee_flexion_l": { "min": 72, "max": 168, "mean": 118 },
      "knee_flexion_r": { "min": 75, "max": 170, "mean": 120 },
      "trunk_flexion_deg": { "mean": 14 }
    }
  },

  "hints": [
    {
      "code": "knee_valgus_mild",
      "severity": "warn",
      "message": "左膝有内扣趋势，膝盖与脚尖方向一致",
      "t_ms": 3200
    }
  ],

  "kb": {
    "searched_at": "2026-10-27T10:00:00Z",
    "similar_refs": [
      {
        "ref_id": "squat_std_01",
        "exercise_id": "squat",
        "similarity": 0.91,
        "source": "pose_kb_json"
      }
    ],
    "quality_score": 0.82,
    "ingested": false,
    "ingest_reason": "score_below_threshold"
  },

  "raw": {
    "format": "coco17",
    "frame_count": 120,
    "note": "与 sequences.coco17.frames 未精炼前一致；实现期可与 optimized 分字段存"
  },

  "optimized": {
    "format": "coco17",
    "frame_count": 120,
    "refiner": "pose_kb_v1"
  }
}
```

实现说明：

- **第一版**可简化为：`sequences.coco17.frames` 同时承担展示；`raw`/`optimized` 用两套 `frames` 或 `optimized` 单独数组。
- `finish` 写入 DB 的 `pose_summary` 至少包含：`sequences`、`angles.summary`、`hints`、`kb`（若已调 `pose_kb`）。

---

## 单帧结构

### MediaPipe-33 帧 `sequences.mediapipe33.frames[]`

```json
{
  "t_ms": 125,
  "frame_index": 1,
  "landmarks": [
    { "i": 0, "name": "nose", "x": 0.52, "y": 0.18, "z": -0.02, "visibility": 0.99 }
  ]
}
```

- `landmarks` 长度 33；`i` 为 MediaPipe 官方索引。
- 可选：只存 `{i,x,y,visibility}` 以减小体积。

### COCO-17 帧 `sequences.coco17.frames[]`

```json
{
  "t_ms": 125,
  "frame_index": 1,
  "keypoints": [
    0.52, 0.18, 2,
    0.51, 0.16, 2,
    0.53, 0.16, 2,
    0.49, 0.17, 2,
    0.55, 0.17, 2,
    0.45, 0.28, 2,
    0.58, 0.27, 2,
    0.42, 0.38, 2,
    0.61, 0.37, 2,
    0.40, 0.48, 2,
    0.63, 0.47, 2,
    0.46, 0.52, 2,
    0.57, 0.52, 2,
    0.47, 0.68, 2,
    0.56, 0.67, 2,
    0.48, 0.85, 2,
    0.55, 0.84, 2
  ],
  "num_keypoints": 17
}
```

- `keypoints`：COCO 惯例 **51 个数** = 17×(x, y, v)。
- **v**：`0` 未标注，`1` 标注不可见，`2` 可见（与 COCO 一致）。

### 每帧派生角 `angles.per_frame[]`（可选，减轻重复计算）

```json
{
  "t_ms": 125,
  "knee_flexion_l": 95,
  "knee_flexion_r": 98,
  "trunk_flexion_deg": 12
}
```

膝角：COCO 左 `(11,13,15)`，右 `(12,14,16)` 三点夹角。

---

## MediaPipe-33 → COCO-17 映射表（`mp33_to_coco17_v1`）

| COCO idx | COCO 名称 | MP idx | 备注 |
|---------|-----------|--------|------|
| 0 | nose | 0 | |
| 1 | left_eye | 2 | 用眼中心，非内外眼角 |
| 2 | right_eye | 5 | |
| 3 | left_ear | 7 | |
| 4 | right_ear | 8 | |
| 5 | left_shoulder | 11 | |
| 6 | right_shoulder | 12 | |
| 7 | left_elbow | 13 | |
| 8 | right_elbow | 14 | |
| 9 | left_wrist | 15 | |
| 10 | right_wrist | 16 | |
| 11 | left_hip | 23 | |
| 12 | right_hip | 24 | |
| 13 | left_knee | 25 | 深蹲主用 |
| 14 | right_knee | 26 | |
| 15 | left_ankle | 27 | |
| 16 | right_ankle | 28 | |

**仅存在于 MediaPipe、无 COCO 点**：脸细点 1,3,4,6,9,10；手 17–22；脚 29–32。保留在 `sequences.mediapipe33` 中，不写入 COCO 数组。

### 可见性映射（建议）

| MediaPipe `visibility` | COCO `v` |
|------------------------|----------|
| &lt; 0.5 或缺失 | 0（x,y 可置 0） |
| 0.5 ~ 0.8 | 1 |
| ≥ 0.8 | 2 |

---

## 一帧转换示例（输入 MP → 输出 COCO 片段）

**输入**（浏览器采集，节选）：

```json
{
  "t_ms": 200,
  "frame_index": 2,
  "landmarks": [
    { "i": 23, "x": 0.46, "y": 0.55, "visibility": 0.95 },
    { "i": 25, "x": 0.47, "y": 0.72, "visibility": 0.93 },
    { "i": 27, "x": 0.48, "y": 0.88, "visibility": 0.90 }
  ]
}
```

**输出**（写入 `sequences.coco17.frames`，仅示意左下肢相关三元组在 51 数组中的位置）：

- 索引 33–35 → left_hip (11)：`[0.46, 0.55, 2]`
- 索引 39–41 → left_knee (13)：`[0.47, 0.72, 2]`
- 索引 45–47 → left_ankle (15)：`[0.48, 0.88, 2]`

完整帧需按映射表填满 17 点；未映射到的 MP 点若 visibility 低，对应 COCO `v=0`。

---

## 与 AI 服务接口

| 服务 | 读 | 写 |
|------|----|----|
| `pose` `/infer` | 单帧图像或关键点 | 可补算 `angles` |
| `pose_kb` `/search` | **`sequences.coco17`**（或 `optimized`） | `similar_refs`, `optimized_sequence`, `quality_score` |
| `pose_kb` `/ingest` | 高分 `optimized` 序列 | 入库 |
| `video_cot` `/evaluate` | `pose_summary` 中 **`optimized` + angles.summary** | — |

---

## 对应申请书

| 申请书 | 本契约字段 |
|--------|------------|
| 图3 姿态估计 | `sequences.*.frames`, `estimator` |
| 图5 知识库检索 + 优化 | `kb`, `optimized`, `refiner` |
| 图6 多骨骼格式 | `capture_format` + `canonical_format` + `converter_version` |
| 运动中引导 | `hints`, `angles` |
| 运动后理解条件 | `optimized` / `angles.summary` → CoT |

---

## 离线视频验证（无需摄像头）

运动页 **输入 → 离线视频**：本地 mp4 等按约 **6Hz** 抽姿态帧，同样写入 `sequences.mediapipe33` / `coco17`，`estimator.runtime = browser_video_file`，`source = offline_video`。

演示样本（RepCount + InfiniteRep）见 [offline_demo_quickstart.md](./offline_demo_quickstart.md)：运动页 **演示样本** 下拉一键加载 `data/demo_videos/`。

## 版本

| 版本 | 说明 |
|------|------|
| 1.0.0 | 双存 MP33 + 主 COCO17；与 `ExerciseSession.pose_summary` 对齐 |
