from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..database import get_db
from ..security import get_current_user, owned_user, require_owner
from ..models.entities import ExerciseSession, Prescription, User
from ..schemas.dto import SessionStartIn, SessionFinishIn
from ..services import ai_client
from ..services.session_completion import complete_session
from ..services.media_access import media_path

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/start")
async def start(body: SessionStartIn, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = require_owner(body.user_id, actor)
    if not user.onboarding_done:
        raise HTTPException(409, "请先完成首次测评")
    # A retry returns the original input and status, never updates or recreates it.
    def previous_start():
        if not body.start_key:
            return None
        previous = db.query(ExerciseSession).filter_by(user_id=user.id, start_key=body.start_key).first()
        if previous and (previous.exercise_id != body.exercise_id or previous.prescription_id != body.prescription_id):
            raise HTTPException(409, "开始请求已用于另一项训练，请先找回原记录")
        return previous

    previous = previous_start()
    if previous:
        return {"session": previous, "pose_live": previous.pose_summary}
    media_path(body.video_path, actor.id)
    plan_snapshot = {}
    exercise_name = body.exercise_name or body.exercise_id
    if body.prescription_id:
        prescription = db.get(Prescription, body.prescription_id)
        if not prescription or prescription.user_id != user.id:
            raise HTTPException(400, "处方不属于当前用户")
        exercise = next((e for e in prescription.exercises or [] if e.get("id") == body.exercise_id), None)
        if not exercise:
            raise HTTPException(400, "所选动作不在这份训练计划中，请重新选择")
        exercise_name = exercise.get("name") or body.exercise_id
        plan_snapshot = {"prescription_id": prescription.id, "version": prescription.version,
                         "status": prescription.status, "exercise": exercise}
    pose = body.pose_summary or await ai_client.pose_infer({"exercise_id": body.exercise_id})
    row = ExerciseSession(
        user_id=user.id,
        start_key=body.start_key,
        prescription_id=body.prescription_id,
        exercise_id=body.exercise_id,
        exercise_name=exercise_name,
        plan_snapshot=plan_snapshot,
        status="running",
        pose_summary=pose,
        video_path=body.video_path,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        previous = previous_start()
        if previous:
            return {"session": previous, "pose_live": previous.pose_summary}
        raise
    db.refresh(row)
    return {"session": row, "pose_live": pose}


def owned_session(db, session_id, user_id):
    row = db.get(ExerciseSession, session_id)
    if not row or row.user_id != user_id:
        raise HTTPException(404, "训练不存在或不属于当前用户")
    return row


@router.get("/{session_id}")
def detail(session_id: int, user_id: int, actor: User = Depends(owned_user), db: Session = Depends(get_db)):
    return {"session": owned_session(db, session_id, user_id)}


@router.post("/{session_id}/cancel")
def cancel(session_id: int, user_id: int, actor: User = Depends(owned_user), db: Session = Depends(get_db)):
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
def save_draft(session_id: int, user_id: int, body: SessionFinishIn, actor: User = Depends(owned_user), db: Session = Depends(get_db)):
    row = owned_session(db, session_id, user_id)
    media_path(body.video_path, actor.id)
    revision = body.expected_revision if body.expected_revision is not None else row.draft_revision
    changed = db.execute(update(ExerciseSession).where(
        ExerciseSession.id == session_id, ExerciseSession.status == "running",
        ExerciseSession.draft_revision == revision
    ).values(video_path=body.video_path, pose_summary=body.pose_summary,
             draft_revision=ExerciseSession.draft_revision + 1).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "训练已结束或已被其他页面更新，请重新打开训练核对，避免覆盖数据")
    db.commit()
    db.refresh(row)
    return {"session": row}


@router.post("/{session_id}/finish")
async def finish(session_id: int, body: SessionFinishIn, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = owned_session(db, session_id, actor.id)
    if row.status == "running":
        media_path(body.video_path or row.video_path, actor.id)
    return await complete_session(db, session_id, body)
