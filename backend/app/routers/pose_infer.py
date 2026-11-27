"""离线视频姿态：转发到 AI pose 服务（RTMPose / rtmlib，COCO-17）。"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import update

from ..config import UPLOAD_DIR
from ..database import get_db
from ..models.entities import ExerciseSession, User
from ..schemas.dto import VideoPoseInferIn
from ..services import ai_client
from ..services.media_access import media_path
from ..security import get_current_user

router = APIRouter(prefix="/pose", tags=["pose"])
logger = logging.getLogger(__name__)

MAX_VIDEO_UPLOAD_BYTES = 100 * 1024 * 1024
MIN_VIDEO_UPLOAD_BYTES = 1000
VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
VIDEO_MIME_SUFFIX = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/webm": ".webm",
    "video/x-matroska": ".mkv",
}


def _upload_suffix(file: UploadFile) -> str:
    """Accept known video names, or use MIME when mobile Safari omits a name."""
    name = (file.filename or "").strip()
    suffix = Path(name).suffix.lower()
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if suffix:
        if suffix not in VIDEO_SUFFIXES:
            raise HTTPException(400, "请选择支持的视频文件")
        if content_type and not content_type.startswith("video/") and content_type != "application/octet-stream":
            raise HTTPException(400, "所选文件不是视频")
        return suffix
    if content_type in VIDEO_MIME_SUFFIX:
        return VIDEO_MIME_SUFFIX[content_type]
    raise HTTPException(400, "无法识别视频格式，请重新拍摄或选择视频")


def _owned_running_session(db: Session, session_id: int, user_id: int) -> ExerciseSession:
    row = db.get(ExerciseSession, session_id)
    if not row or row.user_id != user_id:
        raise HTTPException(404, "训练不存在或不属于当前用户")
    if row.status != "running":
        raise HTTPException(409, "当前训练已经结束，不能继续上传视频")
    return row

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
    result["resolved_path"] = body.video_path.replace("\\", "/")
    return result


@router.post("/infer-video-upload")
async def infer_video_upload(
    file: UploadFile = File(...),
    sample_hz: float = Form(6.0, ge=1.0, le=15.0),
    exercise_id: str | None = Form(None),
    session_id: int | None = Form(None, ge=1),
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _owned_running_session(db, session_id, actor.id) if session_id else None
    previous_video_path = row.video_path if row else ""
    revision = row.draft_revision if row else None
    if row and exercise_id and row.exercise_id != exercise_id:
        raise HTTPException(409, "视频动作与当前训练不一致")
    suffix = _upload_suffix(file)
    dest_dir = UPLOAD_DIR / "offline" / str(actor.id)
    if row:
        dest_dir /= str(row.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = f"{uuid4().hex}{suffix}"
    dest = dest_dir / safe
    temporary = dest.with_suffix(f"{dest.suffix}.part")
    saved = False
    attached = False
    try:
        size = 0
        with temporary.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_VIDEO_UPLOAD_BYTES:
                    raise HTTPException(413, "视频不能超过 100 MB")
                output.write(chunk)
        if size < MIN_VIDEO_UPLOAD_BYTES:
            raise HTTPException(400, "视频文件为空或过小")
        temporary.replace(dest)
        saved = True

        result = await ai_client.pose_infer_video(
            {"video_path": str(dest.resolve()), "sample_hz": sample_hz, "exercise_id": exercise_id}
        )
        if result.get("mode") == "local_fallback":
            raise HTTPException(503, "视频分析服务暂时不可用，请稍后重试")
        if not result.get("coco17_frames"):
            raise HTTPException(502, "视频中没有识别到完整人体，请重新拍摄或选择")

        upload_rel = f"uploads/{str(dest.relative_to(UPLOAD_DIR)).replace(chr(92), '/')}"
        if row:
            changed = db.execute(update(ExerciseSession).where(
                ExerciseSession.id == row.id,
                ExerciseSession.user_id == actor.id,
                ExerciseSession.status == "running",
                ExerciseSession.draft_revision == revision,
            ).values(video_path=upload_rel, draft_revision=revision + 1)
                .execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                raise HTTPException(409, "训练已结束或已在其他页面修改，请重新加载后再上传")
            db.commit()
            attached = True
            expected_prefix = f"uploads/offline/{actor.id}/{row.id}/"
            if previous_video_path.startswith(expected_prefix) and previous_video_path != upload_rel:
                previous = media_path(previous_video_path, actor.id)
                if previous and previous.is_file():
                    try:
                        previous.unlink(missing_ok=True)
                    except OSError:
                        logger.warning("Could not remove superseded session video", exc_info=True)
        result["upload_rel"] = upload_rel
        result["session_id"] = row.id if row else None
        if row:
            result["draft_revision"] = revision + 1
        return result
    except HTTPException:
        if row:
            db.rollback()
        if saved and not attached:
            dest.unlink(missing_ok=True)
        raise
    except Exception:
        if row:
            db.rollback()
        if saved and not attached:
            dest.unlink(missing_ok=True)
        raise HTTPException(502, "视频上传或分析失败，请稍后重试")
    finally:
        temporary.unlink(missing_ok=True)
        await file.close()


@router.get("/estimator")
async def estimator_info():
    return await ai_client.pose_estimator_info()
