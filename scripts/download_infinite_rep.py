"""从 HuggingFace 拉 InfiniteRep 子集并转为 MP4（公开，无需 token）。"""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "datasets" / "InfiniteRep"
REPO = "FatimahEmadEldin/infiniterep-physiotherapy"

TARGETS: list[tuple[str, str]] = [
    ("data/train/squat/000000_img_labels.zip", "squat"),
    ("data/train/squat/000001_img_labels.zip", "squat"),
    ("data/train/squat/000002_img_labels.zip", "squat"),
    ("data/dev/squat/000017_img_labels.zip", "squat"),
    ("data/train/pushup/000000_img_labels.zip", "push_up"),
    ("data/train/pushup/000001_img_labels.zip", "push_up"),
    ("data/train/overheadpress/000000_img_labels.zip", "overhead_press"),
    ("data/train/armraise/000000_img_labels.zip", "arm_raise"),
    ("data/train/legraise/000000_img_labels.zip", "leg_raise"),
]


def _ensure_cv2():
    try:
        import cv2  # noqa: F401
    except ImportError:
        import subprocess
        import sys

        subprocess.check_call([sys.executable, "-m", "pip", "install", "opencv-python-headless", "-q"])
    import cv2

    return cv2


def zip_to_mp4(cv2, zpath: Path, mp4path: Path, fps: int = 15) -> bool:
    tmp = mp4path.parent / f"_tmp_{mp4path.stem}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(tmp)
    imgs = sorted([*tmp.rglob("*.jpg"), *tmp.rglob("*.png"), *tmp.rglob("*.jpeg")])
    if not imgs:
        shutil.rmtree(tmp, ignore_errors=True)
        return False
    im0 = cv2.imread(str(imgs[0]))
    h, w = im0.shape[:2]
    mp4path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(mp4path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for p in imgs:
        im = cv2.imread(str(p))
        if im is None:
            continue
        if im.shape[0] != h or im.shape[1] != w:
            im = cv2.resize(im, (w, h))
        writer.write(im)
    writer.release()
    shutil.rmtree(tmp, ignore_errors=True)
    return True


def main() -> None:
    cv2 = _ensure_cv2()
    manifest: list[dict] = []
    for remote, cls in TARGETS:
        print(f"  {cls} <- {remote}")
        local = Path(
            hf_hub_download(REPO, remote, repo_type="dataset", local_dir=str(OUT / "_cache"))
        )
        zpath = OUT / "zips" / cls / local.name
        zpath.parent.mkdir(parents=True, exist_ok=True)
        if not zpath.exists():
            shutil.copy2(local, zpath)
        mp4 = OUT / "videos" / cls / (local.stem.replace("_img_labels", "") + ".mp4")
        if not mp4.exists() or mp4.stat().st_size < 10_000:
            if not zip_to_mp4(cv2, zpath, mp4):
                print(f"    skip (no frames): {zpath.name}")
                continue
        manifest.append(
            {
                "class": cls,
                "video": str(mp4.relative_to(ROOT)).replace("\\", "/"),
                "source": REPO,
            }
        )
        print(f"    ok {mp4.name} ({mp4.stat().st_size // 1024} KB)")

    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"完成 InfiniteRep: {len(manifest)} 个 mp4")


if __name__ == "__main__":
    main()
