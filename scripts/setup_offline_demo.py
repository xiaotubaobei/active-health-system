"""一键准备离线演示：RepCount + InfiniteRep → demo_videos/manifest.json"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REP = DATA / "datasets" / "RepCount-A" / "squat"
INF = DATA / "datasets" / "InfiniteRep" / "videos"
MANIFEST = DATA / "demo_videos" / "manifest.json"
PY = sys.executable


def _mp4_count(d: Path) -> int:
    return len(list(d.glob("*.mp4"))) if d.is_dir() else 0


def run(script: str) -> None:
    path = ROOT / "scripts" / script
    print(f"\n>> {script}")
    subprocess.check_call([PY, str(path)], cwd=str(ROOT))


def main() -> int:
    print("=== setup_offline_demo ===")

    if _mp4_count(REP) < 3:
        run("download_demo_datasets.py")
    else:
        print(f"RepCount 已有 squat={_mp4_count(REP)}，跳过全量 RepCount 下载")

    inf_n = len(list(INF.rglob("*.mp4"))) if INF.is_dir() else 0
    if inf_n < 2:
        run("download_infinite_rep.py")
    else:
        print(f"InfiniteRep 已有 mp4={inf_n}，跳过")

    run("sync_demo_videos.py")

    print("\n>> verify_offline_demo.py")
    rc = subprocess.call([PY, str(ROOT / "scripts" / "verify_offline_demo.py")], cwd=str(ROOT))
    if rc != 0:
        return rc

    m = MANIFEST.read_text(encoding="utf-8")
    n = m.count('"rel_path"')
    print(f"\n就绪: demo_videos/manifest.json 含 {n} 条")

    try:
        import urllib.request

        urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2)
    except OSError:
        print("\n提示: 后端未启动，跳过 API 冒烟。启动后运行:")
        print("  python scripts/e2e_offline_demo.py")
    else:
        print("\n>> e2e_offline_demo.py（后端已就绪）")
        e2e = subprocess.call([PY, str(ROOT / "scripts" / "e2e_offline_demo.py")], cwd=str(ROOT))
        if e2e != 0:
            return e2e

    print("\n启动: cd backend && uvicorn app.main:app --reload --port 8000")
    print("      cd frontend && npm run dev")
    print("运动页 → 离线视频 → 演示样本 → 开始会话 → 结束并生成报告")
    return 0


if __name__ == "__main__":
    sys.exit(main())
