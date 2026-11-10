from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.entities import ExerciseSession, KbEntry, User
from ..services.kb import kb_summary
from ..services.analysis import analysis_summary

router = APIRouter(prefix="/users", tags=["kb"])


@router.get("/{user_id}/kb/summary")
def summary(user_id: int, limit: int = 20, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    return kb_summary(db, user_id, limit=max(1, min(limit, 100)))


@router.get("/{user_id}/sessions")
def list_sessions(user_id: int, limit: int = 50, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    rows = (
        db.query(ExerciseSession)
        .filter(ExerciseSession.user_id == user_id)
        .order_by(ExerciseSession.id.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [
        {
            "id": s.id,
            "exercise_id": s.exercise_id,
            "exercise_name": s.exercise_name,
            "status": s.status,
            "prescription_id": s.prescription_id,
            "video_path": s.video_path,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "finished_at": s.finished_at.isoformat() if s.finished_at else None,
            "pose_frames": len(
                ((s.pose_summary or {}).get("sequences") or {}).get("coco17", {}).get("frames") or []
            ),
        }
        for s in rows
    ]


@router.get("/{user_id}/kb/entries")
def list_entries(user_id: int, limit: int = 50, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    rows = (
        db.query(KbEntry)
        .filter(KbEntry.user_id == user_id)
        .order_by(KbEntry.id.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    result = []
    for row in rows:
        entry = jsonable_encoder(row)
        entry["analysis"] = analysis_summary(row.multimodal)
        entry["score"] = entry["analysis"]["score"]
        if entry["score"] is None:
            entry["errors"] = []
            entry["advice"] = ""
        result.append(entry)
    return result


@router.delete("/{user_id}/kb")
def clear_kb(user_id: int, confirm: str = "", db: Session = Depends(get_db)):
    """清空某用户 KB（需 confirm=CLEAR）。会话/报告保留。"""
    if confirm != "CLEAR":
        raise HTTPException(400, "请传 confirm=CLEAR 确认清空")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    n = db.query(KbEntry).filter(KbEntry.user_id == user_id).delete()
    db.commit()
    return {"deleted": n, "user_id": user_id}
