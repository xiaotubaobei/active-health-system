"""本地 demo_videos 清单与流媒体（离线验证演示）。"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ..config import DATA_DIR

router = APIRouter(prefix="/demo-videos", tags=["demo-videos"])

DEMO_ROOT = (DATA_DIR / "demo_videos").resolve()


def _manifest_path() -> Path:
    return DEMO_ROOT / "manifest.json"


def _safe_video_path(rel_path: str) -> Path:
    if not rel_path or ".." in rel_path.replace("\\", "/"):
        raise HTTPException(400, "非法路径")
    full = (DEMO_ROOT / rel_path.replace("\\", "/")).resolve()
    if not full.is_relative_to(DEMO_ROOT):
        raise HTTPException(400, "路径越界")
    if not full.is_file() or full.suffix.lower() != ".mp4":
        raise HTTPException(404, "视频不存在")
    return full


@router.get("/manifest")
def get_manifest():
    path = _manifest_path()
    if not path.is_file():
        raise HTTPException(
            503,
            "尚未生成演示清单，请在项目根运行: python scripts/sync_demo_videos.py",
        )
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/file")
def stream_file(rel: str = Query(..., description="manifest.rel_path，如 squat/repcount_stu4_66.mp4")):
    key = rel.replace("\\", "/").lstrip("/")
    for prefix in ("data/demo_videos/", "demo_videos/"):
        if key.startswith(prefix):
            key = key[len(prefix) :]
    target = _safe_video_path(key)
    return FileResponse(
        target,
        media_type="video/mp4",
        filename=target.name,
    )
