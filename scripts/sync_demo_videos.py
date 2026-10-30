"""将 RepCount-A + InfiniteRep 样本同步到 data/demo_videos/ 并生成 manifest.json。"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DEMO = DATA / "demo_videos"
REP = DATA / "datasets" / "RepCount-A"
INF = DATA / "datasets" / "InfiniteRep" / "videos"

# demo 子目录 → 处方 exercise_id（fitness.json）
FOLDER_EXERCISE = {
    "squat": "squat",
    "jump_jack": "jumping_jack",
    "push_up": "pushup",
    "pull_up": "pushup",
    "situp": "squat",
    "arm_raise": "squat",
    "leg_raise": "squat",
    "overhead_press": "squat",
}

MAX_PER_SOURCE = 4


def _prune_legacy_demo_files(dest_dir: Path) -> None:
    """去掉旧版未加前缀的副本，避免与 manifest 不一致。"""
    if not dest_dir.is_dir():
        return
    for f in dest_dir.glob("*.mp4"):
        name = f.name
        if name.startswith(("repcount_", "infinite_", "real_", "fitness_aqa_")):
            continue
        for prefix in ("infinite_", "repcount_"):
            if (dest_dir / f"{prefix}{name}").is_file():
                f.unlink(missing_ok=True)
                break


def _copy_pair(src: Path, dest_dir: Path, prefix: str) -> Path | None:
    if not src.is_file():
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    dst = dest_dir / f"{prefix}{src.name}"
    if not dst.exists() or dst.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dst)
    return dst


def sync() -> dict:
    DEMO.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []

    for folder, exercise_id in FOLDER_EXERCISE.items():
        dest_dir = DEMO / folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        _prune_legacy_demo_files(dest_dir)

        rep_dir = REP / folder
        if rep_dir.is_dir():
            for f in sorted(rep_dir.glob("*.mp4"))[:MAX_PER_SOURCE]:
                dst = _copy_pair(f, dest_dir, "repcount_")
                if dst:
                    entries.append(_entry(folder, exercise_id, dst, "RepCount-A"))

        inf_dir = INF / folder
        if inf_dir.is_dir():
            for f in sorted(inf_dir.glob("*.mp4"))[:MAX_PER_SOURCE]:
                dst = _copy_pair(f, dest_dir, "infinite_")
                if dst:
                    entries.append(_entry(folder, exercise_id, dst, "InfiniteRep"))

    manifest = {
        "version": 1,
        "root": "data/demo_videos",
        "usage": "运动页 → 离线视频 → 选择演示样本",
        "videos": entries,
    }
    out = DEMO / "manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _entry(folder: str, exercise_id: str, path: Path, source: str) -> dict:
    rel = f"{folder}/{path.name}"
    label = f"[{source[:3]}] {rel}"
    return {
        "id": rel.replace("/", "__"),
        "label": label,
        "exercise_id": exercise_id,
        "folder": folder,
        "file_name": path.name,
        "rel_path": rel,
        "source": source,
        "size_bytes": path.stat().st_size,
    }


def main() -> None:
    m = sync()
    print(f"manifest: {len(m['videos'])} 条 -> {DEMO / 'manifest.json'}")
    by_folder: dict[str, int] = {}
    for v in m["videos"]:
        by_folder[v["folder"]] = by_folder.get(v["folder"], 0) + 1
    for k in sorted(by_folder):
        print(f"  {k}: {by_folder[k]}")


if __name__ == "__main__":
    main()
