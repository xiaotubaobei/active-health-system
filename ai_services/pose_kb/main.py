import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _stub import make_app, PoseKbIn

app = make_app("pose_kb")


@app.post("/search")
def search(body: PoseKbIn):
    return {
        "normalized_format": "coco17",
        "input_format": body.skeleton_format,
        "similar": [{"id": "ref_squat_01", "score": 0.91}],
        "optimized_sequence": body.pose_sequence or [{"t": 0, "note": "mock_optimized"}],
        "ingested": False,
        "mode": "mock",
    }


@app.post("/ingest")
def ingest(body: PoseKbIn):
    return {"ok": True, "stored": len(body.pose_sequence), "mode": "mock"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8102)
