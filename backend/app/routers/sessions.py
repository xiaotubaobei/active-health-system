from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.entities import ExerciseSession, Prescription, User
from ..schemas.dto import SessionStartIn, SessionFinishIn
from ..services import ai_client
from ..services.session_completion import complete_session

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/start")
async def start(body: SessionStartIn, db: Session = Depends(get_db)):
    user = db.get(User, body.user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if not user.onboarding_done:
        raise HTTPException(409, "请先完成首次测评")
    if body.prescription_id:
        prescription = db.get(Prescription, body.prescription_id)
        if not prescription or prescription.user_id != user.id:
            raise HTTPException(400, "处方不属于当前用户")
    pose = body.pose_summary or await ai_client.pose_infer({"exercise_id": body.exercise_id})
    row = ExerciseSession(
        user_id=user.id,
        prescription_id=body.prescription_id,
        exercise_id=body.exercise_id,
        exercise_name=body.exercise_name or body.exercise_id,
        status="running",
        pose_summary=pose,
        video_path=body.video_path,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"session": row, "pose_live": pose}


def owned_session(db, session_id, user_id):
    row = db.get(ExerciseSession, session_id)
    if not row or row.user_id != user_id:
        raise HTTPException(404, "训练不存在或不属于当前用户")
    return row


@router.get("/{session_id}")
def detail(session_id: int, user_id: int, db: Session = Depends(get_db)):
    return {"session": owned_session(db, session_id, user_id)}


@router.post("/{session_id}/cancel")
def cancel(session_id: int, user_id: int, db: Session = Depends(get_db)):
    row = owned_session(db, session_id, user_id)
    if row.status == "cancelled":
        return {"session": row}
    changed = db.execute(update(ExerciseSession).where(
        ExerciseSession.id == session_id, ExerciseSession.status == "running"
    ).values(status="cancelled", finished_at=datetime.utcnow()).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "当前训练已结束，不能取消")
    db.commit()
    db.refresh(row)
    return {"session": row}


@router.put("/{session_id}/draft")
def save_draft(session_id: int, user_id: int, body: SessionFinishIn, db: Session = Depends(get_db)):
    row = owned_session(db, session_id, user_id)
    changed = db.execute(update(ExerciseSession).where(
        ExerciseSession.id == session_id, ExerciseSession.status == "running"
    ).values(video_path=body.video_path, pose_summary=body.pose_summary).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "当前训练已结束，不能修改")
    db.commit()
    db.refresh(row)
    return {"session": row}


@router.post("/{session_id}/finish")
async def finish(session_id: int, body: SessionFinishIn, db: Session = Depends(get_db)):
    return await complete_session(db, session_id, body)
