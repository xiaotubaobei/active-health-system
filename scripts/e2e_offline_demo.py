"""无浏览器冒烟：演示 manifest + 登录 + 离线会话 finish（mock 姿态）。"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

API = "http://127.0.0.1:8000"
TOKEN = ""


def _json(method: str, path: str, body: dict | None = None, timeout: float = 60) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    global TOKEN
    print("1) GET /demo-videos/manifest")
    manifest = _json("GET", "/demo-videos/manifest")
    videos = manifest.get("videos") or []
    if len(videos) < 10:
        print(f"FAIL 演示条目过少: {len(videos)}")
        return 1
    pick = next((v for v in videos if v.get("folder") == "squat"), videos[0])
    rel = pick["rel_path"]
    print(f"   选用 {rel}")

    print("2) GET /demo-videos/file")
    req = urllib.request.Request(f"{API}/demo-videos/file?rel={rel}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        blob = resp.read()
    if len(blob) < 10_000:
        print(f"FAIL 视频过小: {len(blob)} bytes")
        return 1
    print(f"   OK {len(blob) // 1024} KB")

    print("3) POST /auth/login (demo)")
    try:
        auth = _json("POST", "/auth/login", {"username": "demo", "password": "123456"})
    except urllib.error.HTTPError as e:
        print(f"FAIL 登录 {e.code}: {e.read().decode()[:200]}")
        return 1
    TOKEN = auth["token"]
    user_id = auth.get("user", {}).get("id") or auth.get("id")
    if not user_id:
        print("FAIL 登录响应无 user_id")
        return 1

    print("4) POST /sessions/start + finish（mock 离线 pose_summary）")
    sess = _json(
        "POST",
        "/sessions/start",
        {
            "user_id": user_id,
            "exercise_id": pick.get("exercise_id", "squat"),
            "exercise_name": "深蹲",
            "prescription_id": 0,
        },
    )
    sid = sess["session"]["id"]
    pose_summary = {
        "schema_version": "1.0.0",
        "exercise_id": pick.get("exercise_id", "squat"),
        "source": "offline_video",
        "estimator": {"runtime": "browser_video_file", "name": "mediapipe_pose"},
        "sequences": {
            "mediapipe33": {"frames": [{"t": 0.0, "landmarks": []}]},
            "coco17": {"frames": [{"t": 0.0, "keypoints": []}]},
        },
    }
    done = _json(
        "POST",
        f"/sessions/{sid}/finish",
        {"video_path": f"demo_videos/{rel}", "pose_summary": pose_summary},
        timeout=90,
    )
    if not done.get("report"):
        print("FAIL finish 无 report", done)
        return 1

    analysis = done.get("analysis") or {}
    print(f"OK  会话 #{sid} 评估状态={analysis.get('status')} 有效评分={analysis.get('score')}")
    print(f"   归档 #{done.get('kb_entry_id')}；此脚本使用 mock 姿态，不验证真实算法。")
    print("\n离线演示链路已打通。浏览器: 运动页 → 离线视频 → 演示样本 → 开始/结束。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.URLError as e:
        print(f"FAIL 无法连接 {API} — 请先: cd backend && uvicorn app.main:app --reload --port 8000")
        print(e)
        sys.exit(1)
