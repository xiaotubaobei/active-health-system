"""冒烟：8101 RTMPose +（可选）后端 /pose/infer-video。"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo_videos" / "squat"
API_POSE = "http://127.0.0.1:8101"
API_BE = "http://127.0.0.1:8000"


def _json(method: str, url: str, body: dict | None = None, timeout: float = 600) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def pick_video() -> Path:
    for p in sorted(DEMO.glob("*.mp4")):
        if p.stat().st_size > 100_000:
            return p
    raise SystemExit(f"无可用 demo 视频: {DEMO}")


def main() -> int:
    print("1) GET", f"{API_POSE}/health")
    try:
        h = _json("GET", f"{API_POSE}/health", timeout=5)
    except urllib.error.URLError as e:
        print("FAIL 请先启动: python ai_services/pose/main.py 或 scripts/start_rtmpose.ps1")
        print(e)
        return 1
    print("  ", h)

    print("2) GET", f"{API_POSE}/estimator")
    print("  ", _json("GET", f"{API_POSE}/estimator", timeout=30))

    video = pick_video()
    print("3) POST /infer/video", video.name)
    out = _json(
        "POST",
        f"{API_POSE}/infer/video",
        {"video_path": str(video), "sample_hz": 4, "exercise_id": "squat"},
        timeout=600,
    )
    n = len(out.get("coco17_frames") or [])
    print(f"   frames={n} estimator={out.get('estimator')}")
    if n < 3:
        print("FAIL 帧数过少")
        return 1

    print("4) 后端 /pose/infer-video（可选）")
    try:
        be = _json(
            "POST",
            f"{API_BE}/pose/infer-video",
            {
                "video_path": f"data/demo_videos/squat/{video.name}",
                "sample_hz": 4,
                "exercise_id": "squat",
            },
            timeout=600,
        )
        print(f"   OK backend frames={len(be.get('coco17_frames') or [])}")
    except urllib.error.URLError:
        print("   SKIP 后端未启动（不影响 8101 冒烟）")

    print("\n通过：本地 RTMPose 可用。前端离线默认 VITE_POSE_OFFLINE=server")
    return 0


if __name__ == "__main__":
    sys.exit(main())
