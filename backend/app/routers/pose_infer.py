"""离线视频姿态：转发到 AI pose 服务（RTMPose / rtmlib，COCO-17）。"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..config import ROOT, UPLOAD_DIR
from ..schemas.dto import VideoPoseInferIn
from ..services import ai_client
from ..services.media_access import media_path
from ..security import get_current_user
from ..models.entities import User

router = APIRouter(prefix="/pose", tags=["pose"])

@router.post("/infer-video")
async def infer_video(body: VideoPoseInferIn, actor: User = Depends(get_current_user)):
    path = media_path(body.video_path, actor.id, must_exist=True)
    result = await ai_client.pose_infer_video(
        {"video_path": str(path), "sample_hz": body.sample_hz, "exercise_id": body.exercise_id}
    )
    if result.get("mode") == "local_fallback":
        raise HTTPException(
            503,
            result.get("error") or "姿态服务不可用，请启动: python ai_services/pose/main.py 或 run_ai_stubs.py",
        )
    if not result.get("coco17_frames"):
        raise HTTPException(502, "RTMPose 未返回有效关键点")
    try:
        result["resolved_path"] = str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        result["resolved_path"] = str(path)
    return result


@router.post("/infer-video-upload")
async def infer_video_upload(
    file: UploadFile = File(...),
    sample_hz: float = Form(6.0, ge=1.0, le=15.0),
    exercise_id: str | None = Form(None),
    actor: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(400, "缺少文件名")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".mp4", ".mov", ".avi", ".webm", ".mkv"}:
        raise HTTPException(400, "请上传支持的视频格式")
    dest_dir = UPLOAD_DIR / "offline" / str(actor.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = f"{uuid4().hex}{suffix}"
    dest = dest_dir / safe
    limit = 100 * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, "视频不能超过 100 MB")
    if len(data) < 1000:
        raise HTTPException(400, "文件过小")
    dest.write_bytes(data)

    result = await ai_client.pose_infer_video(
        {"video_path": str(dest.resolve()), "sample_hz": sample_hz, "exercise_id": exercise_id}
    )
    if result.get("mode") == "local_fallback":
        raise HTTPException(503, result.get("error") or "姿态服务不可用")
    result["upload_rel"] = f"uploads/offline/{actor.id}/{safe}"
    return result


@router.get("/estimator")
async def estimator_info():
    return await ai_client.pose_estimator_info()
