import sys
from pathlib import Path

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _stub import make_app, PoseInferIn
from pydantic import BaseModel, Field

app = make_app("pose")
app.version = "0.2.0-rtmpose"


class VideoPoseIn(BaseModel):
    video_path: str
    sample_hz: float = Field(default=6.0, ge=1.0, le=15.0)
    exercise_id: str | None = None


@app.post("/infer")
def infer(body: PoseInferIn):
    return {
        "keypoints": [[0.5, 0.2, 0.9]],
        "angles": {"knee_left": 95.0},
        "hints": ["单帧 infer 请用 POST /infer/video"],
        "exercise_id": body.exercise_id,
        "mode": "stub_single_frame",
    }


@app.post("/infer/video")
def infer_video(body: VideoPoseIn):
    from rtmpose_runner import process_video

    p = Path(body.video_path)
    if not p.is_file():
        raise HTTPException(404, f"视频不存在: {body.video_path}")
    try:
        data = process_video(p, sample_hz=body.sample_hz)
    except RuntimeError as e:
        raise HTTPException(422, str(e)) from e
    data["exercise_id"] = body.exercise_id
    return data


@app.get("/estimator")
def estimator_info():
    from rtmpose_runner import RTM_BACKEND, RTM_MODE, estimator_name

    return {
        "estimator": estimator_name(),
        "rtm_mode": RTM_MODE,
        "backend": RTM_BACKEND,
        "format": "coco17",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8101)
