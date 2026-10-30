"""下载离线验证用健身视频子集到 data/datasets/。

RepCount-A 真实 MP4：从公开 Lance 包提取（无需 HF 登录）
  lmms-lab-eval/repcounta-lance

可选：设置 HF_TOKEN 后尝试 momo321654/RepCountA-videos 直链（常需登录）。

另补 Pexels 等公开真实深蹲片段到 public_real/。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import lance

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "datasets"
DEMO = ROOT / "data" / "demo_videos"
LANCE_BASE = "hf://datasets/lmms-lab-eval/repcounta-lance/data"
MP4_REPO = "momo321654/RepCountA-videos"

WANTED = {
    "squat": ["squat", "squant"],
    "jump_jack": ["jump_jack", "jumpjack", "jumpjacks", "jumping_jack"],
    "push_up": ["push_up", "pushup", "push_ups"],
    "situp": ["situp", "sit_up", "sit-up"],
    "pull_up": ["pull_up", "pullup", "pull_ups"],
}

MAX_PER_CLASS = 6
LANCE_SPLITS = ["train", "validation", "test"]

# 免费可商用（Pexels License），经 yt-dlp 拉取
PUBLIC_SQUAT_URLS = [
    ("https://www.pexels.com/video/a-woman-doing-squats-8837118/", "pexels_8837118_woman_squats.mp4"),
    ("https://www.pexels.com/video/man-doing-barbell-squats-5319755/", "pexels_5319755_barbell_squats.mp4"),
    ("https://www.pexels.com/video/woman-doing-squats-4838220/", "pexels_4838220_squats.mp4"),
]


def _norm(s: str) -> str:
    return (s or "").lower().replace("-", "_").replace(" ", "_")


def match_class(action_type: str) -> str | None:
    a = _norm(action_type)
    for cls, keys in WANTED.items():
        for k in keys:
            if k in a or a == k:
                return cls
    return None


def _lance_action_filter() -> str:
    types: set[str] = set()
    for keys in WANTED.values():
        types.update(keys)
    inner = ", ".join(f"'{t}'" for t in sorted(types))
    return f"action_type IN ({inner})"


def extract_repcount_from_lance() -> dict:
    counts = {k: 0 for k in WANTED}
    manifest: dict = {
        "source": "lmms-lab-eval/repcounta-lance",
        "classes": {k: [] for k in WANTED},
        "videos": [],
    }

    for split in LANCE_SPLITS:
        if all(counts[k] >= MAX_PER_CLASS for k in WANTED):
            break
        uri = f"{LANCE_BASE}/{split}.lance"
        print(f"  Lance {split} …")
        ds = lance.dataset(uri)
        meta = ds.to_table(
            columns=["video_id", "source_name", "action_type", "count", "split"],
            filter=_lance_action_filter(),
        )
        pending_indices: list[int] = []
        pending_rows: list[dict] = []
        for i in range(meta.num_rows):
            action = meta.column("action_type")[i].as_py()
            cls = match_class(action)
            if not cls or counts[cls] >= MAX_PER_CLASS:
                continue
            pending_indices.append(i)
            pending_rows.append(
                {
                    "class": cls,
                    "video_id": meta.column("video_id")[i].as_py(),
                    "source_name": meta.column("source_name")[i].as_py(),
                    "action_type": action,
                    "count": meta.column("count")[i].as_py(),
                    "split": meta.column("split")[i].as_py() or split,
                }
            )
            counts[cls] += 1
            if all(counts[k] >= MAX_PER_CLASS for k in WANTED):
                break

        if not pending_indices:
            continue

        blob_pairs = ds.read_blobs("video_blob", indices=pending_indices)
        for (_, blob_bytes), row in zip(blob_pairs, pending_rows, strict=True):
            if not blob_bytes:
                counts[row["class"]] -= 1
                continue
            fname = Path(row["source_name"] or f"{row['video_id']}.mp4").name
            dest_dir = OUT / "RepCount-A" / row["class"]
            dest_dir.mkdir(parents=True, exist_ok=True)
            dst = dest_dir / fname
            if not dst.exists() or dst.stat().st_size != len(blob_bytes):
                dst.write_bytes(blob_bytes)
            entry = {
                "class": row["class"],
                "path": str(dst.relative_to(ROOT)).replace("\\", "/"),
                "split": row["split"],
                "action_type": row["action_type"],
                "count": row["count"],
                "video_id": row["video_id"],
            }
            manifest["classes"][row["class"]].append(entry)
            manifest["videos"].append(entry)
            print(f"     ok [{row['class']}] {fname} (count={row['count']})")

    man_path = OUT / "RepCount-A" / "manifest.json"
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def try_mp4_repo_fallback(manifest: dict) -> None:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    if not token:
        return
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        return

    print("3) 可选：HF token 存在，跳过 Lance 已覆盖项…")
    for entry in list(manifest.get("videos", [])):
        cls = entry["class"]
        if counts_full(manifest, cls):
            continue
        split = entry.get("split", "train")
        fname = Path(entry["path"]).name
        try:
            path = hf_hub_download(
                MP4_REPO,
                f"{split}/{fname}",
                repo_type="dataset",
                token=token,
                local_dir=str(OUT / "RepCount-A" / "_cache_mp4"),
            )
            dst = OUT / "RepCount-A" / cls / fname
            shutil.copy2(path, dst)
        except Exception as e:  # noqa: BLE001
            print(f"     HF mp4 skip {fname}: {e}")


def counts_full(manifest: dict, cls: str) -> bool:
    return len(manifest.get("classes", {}).get(cls, [])) >= MAX_PER_CLASS


def download_public_squats() -> list[dict]:
    """可选：Pexels 等站点多半有 Cloudflare，失败时不影响 RepCount 主流程。"""
    dest_dir = OUT / "public_real" / "squat"
    dest_dir.mkdir(parents=True, exist_ok=True)
    demo_squat = DEMO / "squat"
    demo_squat.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []

    print("4) 可选 Pexels 公开深蹲（常因 403 跳过）…")
    for url, filename in PUBLIC_SQUAT_URLS:
        dst = dest_dir / filename
        if dst.exists() and dst.stat().st_size > 100_000:
            entries.append(
                {
                    "class": "squat",
                    "path": str(dst.relative_to(ROOT)).replace("\\", "/"),
                    "source": "pexels",
                    "url": url,
                }
            )
            continue
        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            "-f",
            "best[ext=mp4]/best",
            "--no-playlist",
            "--extractor-args",
            "generic:impersonate=chrome",
            "-o",
            str(dst),
            url,
        ]
        print(f"     ↓ {filename}")
        rc = subprocess.run(cmd, check=False).returncode
        if rc != 0 or not dst.exists() or dst.stat().st_size < 100_000:
            print(f"     跳过 {filename}（网络/反爬）")
            continue
        demo_path = demo_squat / f"real_{filename}"
        if not demo_path.exists():
            shutil.copy2(dst, demo_path)
        entries.append(
            {
                "class": "squat",
                "path": str(dst.relative_to(ROOT)).replace("\\", "/"),
                "source": "pexels",
                "url": url,
            }
        )

    if entries:
        man = OUT / "public_real" / "manifest.json"
        man.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    return entries


def ensure_fitness_aqa_readme() -> None:
    d = OUT / "Fitness-AQA"
    d.mkdir(parents=True, exist_ok=True)
    readme = d / "README.md"
    if readme.exists():
        return
    readme.write_text(
        """# Fitness-AQA（需申请）

1. 填写申请表：https://forms.gle/PbPTX1eVxGpa3QG88
2. 收到作者提供的下载链接后，将视频解压/放入本目录
3. 参考官方仓库：https://github.com/ParitoshParmar/Fitness-AQA

本目录仅作占位，不含受版权保护的视频文件。
""",
        encoding="utf-8",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ensure_fitness_aqa_readme()

    print("1) 从 RepCount Lance 提取真实 MP4（公开，无需登录）…")
    manifest = extract_repcount_from_lance()
    print(f"   RepCount 视频: {len(manifest['videos'])}")

    try_mp4_repo_fallback(manifest)

    print("2) 同步 demo_videos + manifest.json …")
    import sys

    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from sync_demo_videos import sync as sync_demo  # noqa: WPS433

    demo_manifest = sync_demo()
    print(f"   演示条目: {len(demo_manifest['videos'])}")

    public = download_public_squats()
    print(f"   公开真实深蹲: {len(public)}")

    print("\n完成")
    for cls, lst in manifest["classes"].items():
        if lst:
            print(f"  RepCount {cls}: {len(lst)}")
    print(f"  清单: {OUT / 'RepCount-A' / 'manifest.json'}")


if __name__ == "__main__":
    main()
