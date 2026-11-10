from fastapi import APIRouter, Depends, HTTPException
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
    pose = await ai_client.pose_infer({"exercise_id": body.exercise_id})
    row = ExerciseSession(
        user_id=user.id,
        prescription_id=body.prescription_id,
        exercise_id=body.exercise_id,
        exercise_name=body.exercise_name or body.exercise_id,
        status="running",
        pose_summary=pose,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"session": row, "pose_live": pose}


@router.post("/{session_id}/finish")
async def finish(session_id: int, body: SessionFinishIn, db: Session = Depends(get_db)):
    return await complete_session(db, session_id, body)
