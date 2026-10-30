"""校验 RepCount + InfiniteRep + demo_videos 离线演示是否就绪。"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DEMO = DATA / "demo_videos"
REP = DATA / "datasets" / "RepCount-A"
INF = DATA / "datasets" / "InfiniteRep" / "videos"
MANIFEST = DEMO / "manifest.json"
API = "http://127.0.0.1:8000"


def _count_mp4(d: Path) -> int:
    return len(list(d.rglob("*.mp4"))) if d.is_dir() else 0


def check_files() -> list[str]:
    errors: list[str] = []
    rep_n = sum(_count_mp4(REP / sub) for sub in ("squat", "jump_jack", "push_up") if (REP / sub).is_dir())
    inf_n = _count_mp4(INF)
    if rep_n < 3:
        errors.append(f"RepCount-A 样本过少（mp4={rep_n}），请运行: python scripts/download_demo_datasets.py")
    if inf_n < 2:
        errors.append(f"InfiniteRep 样本过少（mp4={inf_n}），请运行: python scripts/download_demo_datasets.py")
    if not MANIFEST.is_file():
        errors.append("缺少 demo_videos/manifest.json，请运行: python scripts/sync_demo_videos.py")
        return errors
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    videos = manifest.get("videos") or []
    if len(videos) < 10:
        errors.append(f"manifest 条目过少（{len(videos)}），请运行: python scripts/sync_demo_videos.py")
    missing = []
    for v in videos:
        rel = v.get("rel_path", "")
        p = DEMO / rel.replace("/", "\\")
        if not p.is_file():
            missing.append(rel)
    if missing:
        errors.append(f"manifest 中有 {len(missing)} 个文件缺失，请重新 sync")
    return errors


def check_api() -> list[str]:
    errors: list[str] = []
    try:
        req = urllib.request.Request(f"{API}/demo-videos/manifest")
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode())
        if not body.get("videos"):
            errors.append("后端 /demo-videos/manifest 返回空列表")
        rel = body["videos"][0]["rel_path"]
        file_req = urllib.request.Request(f"{API}/demo-videos/file?rel={rel}")
        with urllib.request.urlopen(file_req, timeout=30) as resp:
            if resp.status != 200 or int(resp.headers.get("Content-Length", 1)) < 1000:
                errors.append("演示视频流媒体接口异常")
    except urllib.error.URLError:
        errors.append(
            f"后端未启动或不可达（{API}）。离线演示需: cd backend && uvicorn app.main:app --reload --port 8000"
        )
    return errors


def main() -> int:
    print("=== 离线演示数据检查 ===")
    file_errs = check_files()
    if file_errs:
        for e in file_errs:
            print("FAIL", e)
    else:
        m = json.loads(MANIFEST.read_text(encoding="utf-8"))
        print(f"OK  manifest: {len(m['videos'])} 条演示视频")
        print(f"OK  RepCount + InfiniteRep 目录存在")

    print("\n=== 后端 API（可选，需已启动）===")
    api_errs = check_api()
    if api_errs:
        for e in api_errs:
            print("WARN", e)
    else:
        print("OK  /demo-videos/manifest 与 file 可访问")

    if file_errs:
        return 1
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ready = {
        "ready": True,
        "video_count": len(m.get("videos") or []),
        "sources": ["RepCount-A", "InfiniteRep"],
        "manifest": "data/demo_videos/manifest.json",
    }
    (DEMO / "READY.json").write_text(
        json.dumps(ready, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n通过：{ready['video_count']} 条演示样本已就绪（已写入 demo_videos/READY.json）")
    print("运动页 → 离线视频 → 演示样本 → 开始会话 → 结束并生成报告")
    print("详见 docs/offline_demo_quickstart.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
