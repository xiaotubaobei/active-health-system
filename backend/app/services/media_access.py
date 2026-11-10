"""Resolve public demonstration media or the current user's uploads only."""
from pathlib import Path

from fastapi import HTTPException

from ..config import ROOT, DATA_DIR, UPLOAD_DIR


def media_path(reference: str, user_id: int, *, must_exist: bool = False) -> Path | None:
    raw = reference.replace("\\", "/").strip()
    if not raw:
        if must_exist:
            raise HTTPException(400, "请选择视频")
        return None
    if ".." in Path(raw).parts:
        raise HTTPException(400, "媒体路径无效")
    if raw.startswith("demo_videos/"):
        path = DATA_DIR / raw
    else:
        path = ROOT / raw
    path = path.resolve()
    allowed = (DATA_DIR / "demo_videos").resolve(), (UPLOAD_DIR / "offline" / str(user_id)).resolve()
    if not any(path.is_relative_to(root) for root in allowed):
        raise HTTPException(404, "媒体不存在或无权访问，请重新上传自己的文件")
    if must_exist and not path.is_file():
        raise HTTPException(404, "媒体文件不存在，请重新上传")
    return path
