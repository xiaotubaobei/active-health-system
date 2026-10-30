"""本地 RTMPose：依赖 + 单视频推理 + 经后端转发（需 8101 与 8000 已启动）。"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "demo_videos" / "squat" / "repcount_stu4_66.mp4"


def main() -> int:
    print("=== RTMPose 本地校验 ===")
    if not SAMPLE.is_file():
        print(f"FAIL 缺少样本: {SAMPLE}")
        print("  运行: python scripts/setup_offline_demo.py")
        return 1

    sys.path.insert(0, str(ROOT / "ai_services" / "pose"))
    try:
        from rtmpose_runner import process_video, RTM_BACKEND

        print(f"1) 直连 runner（backend={RTM_BACKEND}）…")
        data = process_video(SAMPLE, sample_hz=3)
        n = len(data.get("coco17_frames") or [])
        print(f"   OK  {n} 帧 COCO-17 · {data.get('estimator', {}).get('name')}")
    except Exception as e:
        print(f"FAIL runner: {e}")
        print("  尝试: pip install -r ai_services/pose/requirements.txt")
        print("  OpenCV 须 <5；Windows 默认 opencv DNN，可设 RTMPOSE_BACKEND=onnxruntime")
        return 1

    print("2) GET http://127.0.0.1:8101/estimator …")
    try:
        with urllib.request.urlopen("http://127.0.0.1:8101/estimator", timeout=5) as r:
            print("   ", json.loads(r.read().decode()))
    except urllib.error.URLError as e:
        print(f"   WARN pose 服务未起: {e}")
        print("   启动: cd ai_services/pose && python main.py")
        print("   或: python scripts/run_ai_stubs.py")

    print("3) POST http://127.0.0.1:8000/pose/infer-video …")
    body = json.dumps(
        {"video_path": f"data/demo_videos/squat/{SAMPLE.name}", "sample_hz": 3, "exercise_id": "squat"}
    ).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8000/pose/infer-video",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            resp = json.loads(r.read().decode())
        print(f"   OK  {len(resp.get('coco17_frames') or [])} 帧")
    except urllib.error.URLError as e:
        print(f"   WARN 后端未起或未连 pose: {e}")
        return 0

    print("\n通过：运动页离线模式默认 VITE_POSE_OFFLINE=server，选演示样本即可走 RTMPose。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
