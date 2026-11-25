"""Account-scoped, versioned self reports; never used as measured algorithm output."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.entities import SessionFeedback, User
from ..schemas.dto import SessionFeedbackIn
from ..security import get_current_user
from .sessions import owned_session

router = APIRouter(prefix="/sessions", tags=["feedback"])
CONFLICT = "这条反馈已在其他页面更新，请先重新加载，核对后再保存。"


@router.get("/{session_id}/feedback")
def get_feedback(session_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = owned_session(db, session_id, actor.id)
    if row.status != "finished":
        raise HTTPException(409, "请先结束训练，再填写反馈")
    return {"feedback": db.get(SessionFeedback, session_id)}


@router.put("/{session_id}/feedback")
def save_feedback(session_id: int, body: SessionFeedbackIn, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = owned_session(db, session_id, actor.id)
    if session.status != "finished":
        raise HTTPException(409, "请先结束训练，再填写反馈")
    values = body.model_dump(exclude={"expected_revision"})
    previous = db.get(SessionFeedback, session_id)

    def same_submission(row):
        # A lost response can be retried once against the same revision without duplicating edits.
        return (row is not None and row.revision in {body.expected_revision, body.expected_revision + 1}
                and all(getattr(row, key) == value for key, value in values.items()))

    if same_submission(previous):
        return {"feedback": previous}
    if previous is None and body.expected_revision == 0:
        row = SessionFeedback(session_id=session_id, user_id=actor.id, **values)
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            row = db.get(SessionFeedback, session_id)
            if not same_submission(row):
                raise HTTPException(409, CONFLICT)
        db.refresh(row)
        return {"feedback": row}
    changed = db.execute(update(SessionFeedback).where(
        SessionFeedback.session_id == session_id,
        SessionFeedback.user_id == actor.id,
        SessionFeedback.revision == body.expected_revision,
    ).values(**values, revision=body.expected_revision + 1, updated_at=datetime.utcnow())
        .execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.rollback()
        row = db.get(SessionFeedback, session_id)
        if same_submission(row):
            return {"feedback": row}
        raise HTTPException(409, CONFLICT)
    db.commit()
    return {"feedback": db.get(SessionFeedback, session_id, populate_existing=True)}
