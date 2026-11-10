from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.entities import BehaviorReport, ExerciseSession, User
from ..security import get_current_user

from ..services.analysis import analysis_summary

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{session_id}")
def get_report(session_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = db.query(BehaviorReport).filter(BehaviorReport.session_id == session_id, BehaviorReport.user_id == actor.id).first()
    if not report:
        raise HTTPException(404, "报告不存在，请先结束运动会话")
    session = db.get(ExerciseSession, session_id)
    return {"session": session, "report": report, "analysis": analysis_summary(report.cot)}
