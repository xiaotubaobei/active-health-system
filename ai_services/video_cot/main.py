import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _stub import make_app, VideoCotIn

app = make_app("video_cot")


@app.post("/evaluate")
def evaluate(body: VideoCotIn):
    name = body.exercise_name or "动作"
    steps = [
        f"1) 划分阶段：准备 → 离心 → 向心 → 还原（针对{name}）",
        "2) 对照标准：膝踝对齐基本合格，躯干前倾略大",
        "3) 安全风险：轻度膝内扣风险，建议关注落地/下蹲轨迹",
        "4) 完成度评分：78/100",
        "5) 处方建议：下周同动作组数维持，增加2组矫正激活",
    ]
    return {
        "steps": steps,
        "score": 78.0,
        "errors": ["knee_valgus_mild", "trunk_lean"],
        "advice": "保持脊柱中立；下蹲时膝盖朝向脚尖；可加入臀中肌激活。",
        "raw_cot": "\n".join(steps),
        "pose_summary_used": bool(body.pose_summary),
        "parsing_summary_used": bool(body.parsing_summary),
        "mode": "mock",
        "note": "框架桩；后续替换为 Video-R2 权重推理",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8107)
