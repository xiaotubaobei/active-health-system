"""检查 / 解压 Fitness-AQA 到 data/datasets/Fitness-AQA/，并复制少量 BackSquat 到 demo_videos。"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "datasets" / "Fitness-AQA"
DEMO = ROOT / "data" / "demo_videos" / "squat"
ARCHIVE_EXTS = {".zip", ".tar", ".gz", ".tgz", ".7z", ".rar"}


def find_archives() -> list[Path]:
    if not DEST.is_dir():
        return []
    out: list[Path] = []
    for p in DEST.iterdir():
        if p.is_file() and p.suffix.lower() in ARCHIVE_EXTS:
            out.append(p)
        if p.is_file() and p.name.endswith(".tar.gz"):
            out.append(p)
    return out


def count_media(root: Path) -> tuple[int, int]:
    mp4 = list(root.rglob("*.mp4"))
    jsons = list(root.rglob("*.json"))
    return len(mp4), len(jsons)


def extract_zips() -> None:
    for arc in find_archives():
        if arc.suffix.lower() != ".zip":
            print(f"  请手动解压: {arc.name}")
            continue
        target = DEST / arc.stem
        if target.is_dir() and any(target.rglob("*.mp4")):
            print(f"  已解压过: {arc.name} -> {target.name}/")
            continue
        print(f"  解压 {arc.name} …")
        with zipfile.ZipFile(arc, "r") as zf:
            zf.extractall(DEST)


def copy_backsquat_demos(max_n: int = 4) -> int:
    mp4s = sorted(DEST.rglob("*.mp4"))
    picks = [
        p
        for p in mp4s
        if any(k in p.as_posix().lower() for k in ("backsquat", "back_squat", "squat"))
    ][:max_n]
    if not picks:
        picks = mp4s[:max_n]
    DEMO.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in picks:
        dst = DEMO / f"fitness_aqa_{p.stem}.mp4"
        if not dst.exists() or dst.stat().st_size != p.stat().st_size:
            shutil.copy2(p, dst)
        n += 1
    return n


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    print(f"目录: {DEST}")
    archives = find_archives()
    mp4_n, json_n = count_media(DEST)
    print(f"当前: mp4={mp4_n}, json={json_n}, 压缩包={len(archives)}")

    if archives:
        extract_zips()
        mp4_n, json_n = count_media(DEST)

    if mp4_n == 0:
        print(
            "\n尚未检测到视频。填表后请：\n"
            "  1) 查邮箱（含垃圾箱）是否收到作者回复的 Google Drive 链接\n"
            "  2) 下载压缩包到本目录，或解压后的文件夹放在本目录下\n"
            "  3) 再运行: python scripts/ingest_fitness_aqa.py\n"
        )
        return

    n = copy_backsquat_demos()
    print(f"\n已就绪: {mp4_n} 个 mp4；已复制 {n} 个到 {DEMO.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
