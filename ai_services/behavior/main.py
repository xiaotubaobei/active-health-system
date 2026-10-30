import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _stub import make_app, BehaviorIn

app = make_app("behavior")


@app.post("/infer")
def infer(body: BehaviorIn):
    task = body.task
    base = {"task": task, "exercise_name": body.exercise_name, "mode": "mock"}
    if task == "recognize":
        return {**base, "class": body.exercise_name or "squat", "confidence": 0.88}
    if task == "localize":
        return {**base, "segments": [{"start": 1.2, "end": 4.5, "label": body.exercise_name or "action"}]}
    if task == "segment":
        return {**base, "mask_timeline": [{"t": 0, "label": "bg"}, {"t": 1, "label": "action"}]}
    if task == "assess":
        return {**base, "score": 78.0, "errors": ["knee_valgus_mild"]}
    if task == "describe":
        return {
            **base,
            "description": f"mock: 受试者正在完成{body.exercise_name or '动作'}，整体节奏稳定。",
        }
    return {**base, "error": "unknown_task"}


@app.post("/infer_all")
def infer_all(body: BehaviorIn):
    results = {}
    for t in ["recognize", "localize", "segment", "assess", "describe"]:
        body.task = t
        results[t] = infer(body)
    return {"tasks": results, "mode": "mock"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8106)
