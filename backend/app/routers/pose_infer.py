"""离线视频姿态：转发到 AI pose 服务（RTMPose / rtmlib，COCO-17）。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import DATA_DIR, ROOT, UPLOAD_DIR
from ..schemas.dto import VideoPoseInferIn
from ..services import ai_client

router = APIRouter(prefix="/pose", tags=["pose"])

_ALLOWED_ROOTS = tuple({p.resolve() for p in (DATA_DIR, UPLOAD_DIR, ROOT / "data")})


def _resolve_video_path(video_path: str) -> Path:
    raw = video_path.replace("\\", "/").strip()
    if not raw or ".." in raw:
        raise HTTPException(400, "非法 video_path")

    rel = raw
    if rel.startswith("data/"):
        rel = rel[5:]

    candidates = [
        Path(raw),
        ROOT / raw,
        ROOT / rel,
        DATA_DIR / rel,
        DATA_DIR.parent / rel,
    ]
    for cand in candidates:
        if not cand.is_file():
            continue
        full = cand.resolve()
        if any(str(full).startswith(str(root)) for root in _ALLOWED_ROOTS):
            return full
    raise HTTPException(404, f"视频不存在: {video_path}")


@router.post("/infer-video")
async def infer_video(body: VideoPoseInferIn):
    path = _resolve_video_path(body.video_path)
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
    sample_hz: float = Form(6.0),
    exercise_id: str | None = Form(None),
):
    if not file.filename:
        raise HTTPException(400, "缺少文件名")
    dest_dir = UPLOAD_DIR / "offline"
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = Path(file.filename).name
    dest = dest_dir / safe
    data = await file.read()
    if len(data) < 1000:
        raise HTTPException(400, "文件过小")
    dest.write_bytes(data)

    result = await ai_client.pose_infer_video(
        {"video_path": str(dest.resolve()), "sample_hz": sample_hz, "exercise_id": exercise_id}
    )
    if result.get("mode") == "local_fallback":
        raise HTTPException(503, result.get("error") or "姿态服务不可用")
    result["upload_rel"] = f"uploads/offline/{safe}"
    return result


@router.get("/estimator")
async def estimator_info():
    return await ai_client.pose_estimator_info()
