"""演示训练归档；无处方时创建初始模板，训练后不自动调整处方。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import get_current_user, require_owner
from ..models.entities import User, Prescription, ExerciseSession
from ..schemas.dto import SessionFinishIn
from ..services.prescription import pick_template
from ..services.session_completion import complete_session

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoLoopIn(BaseModel):
    user_id: int
    exercise_id: str = "squat"
    exercise_name: str = "深蹲"


@router.post("/run-loop")
async def run_loop(body: DemoLoopIn, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = require_owner(body.user_id, actor)
    if not user.onboarding_done:
        raise HTTPException(409, "请先完成首次测评")
    presc = db.query(Prescription).filter_by(user_id=user.id).order_by(Prescription.version.desc()).first()
    if not presc:
        _, payload = pick_template(user.age_group, user.goal, user.chronic_tags or [])
        presc = Prescription(user_id=user.id, version=1, status="pre_prescription",
                             notes="演示使用的初始模板处方，非模型评估生成", **payload)
        db.add(presc)
        db.flush()
    session = ExerciseSession(
        user_id=user.id, prescription_id=presc.id,
        exercise_id=body.exercise_id, exercise_name=body.exercise_name,
        status="running", pose_summary={"source": "demo"},
    )
    db.add(session)
    db.commit()
    result = await complete_session(
        db, session.id, SessionFinishIn(video_path="", pose_summary={"source": "demo"}), demo=True,
    )
    db.refresh(presc)
    return {
        **result, "ok": True, "session_id": session.id, "prescription": presc,
        "message": "演示训练已归档，可查看报告与历史记录；演示分数不计入成绩，处方未调整。",
    }
