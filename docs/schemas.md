# 核心 JSON Schema（框架冻结）

## 运动会话姿态 `pose_summary`

双格式：**MediaPipe-33 原始** + **主格式 COCO-17**（KB、CoT、处方规则默认读 COCO）。

完整字段、映射表与样例见 **[pose_session.md](pose_session.md)**。

## Video CoT 输出 `cot`

```json
{
  "steps": ["1) ...", "2) ..."],
  "score": 78.0,
  "errors": ["knee_valgus_mild"],
  "advice": "文本建议",
  "raw_cot": "完整推理原文",
  "mode": "mock|remote"
}
```

## 行为理解五任务 `tasks`

```json
{
  "recognize": {"class": "squat", "confidence": 0.88},
  "localize": {"segments": [{"start": 1.2, "end": 4.5, "label": "squat"}]},
  "segment": {"mask_timeline": [{"t": 0, "label": "bg"}]},
  "assess": {"score": 78.0, "errors": ["knee_valgus_mild"]},
  "describe": {"description": "..."}
}
```

## 处方对象（对齐申请书要素）

| 字段 | 含义 |
|---|---|
| mode | 运动方式 |
| intensity | 强度 |
| frequency | 频次 |
| duration | 时长 |
| cycle | 周期 |
| volume | 总量 |
| progression | 进阶 |
| exercises | 动作列表 |
| health_plan | medication / psychology / diet / sleep |
| status | 图15状态机 |

## 处方状态机

`clinical_intake` → `fitness_assessed` → `pre_prescription` → `monitoring` → `formal_prescription` → `implementing` → `feedback`
