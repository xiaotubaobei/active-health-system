import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _stub import make_app, VideoGenIn

app = make_app("video_gen")


@app.post("/generate")
def generate(body: VideoGenIn):
    return {
        "status": "queued_mock",
        "output_video": "uploads/mock_generated.mp4",
        "labels": {"pose_guided": True, "prompt": body.prompt},
        "mode": "mock",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8103)
