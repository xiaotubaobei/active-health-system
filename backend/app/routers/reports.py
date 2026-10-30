from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.entities import BehaviorReport, ExerciseSession

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{session_id}")
def get_report(session_id: int, db: Session = Depends(get_db)):
    report = db.query(BehaviorReport).filter(BehaviorReport.session_id == session_id).first()
    if not report:
        raise HTTPException(404, "报告不存在，请先结束运动会话")
    session = db.get(ExerciseSession, session_id)
    return {"session": session, "report": report}
