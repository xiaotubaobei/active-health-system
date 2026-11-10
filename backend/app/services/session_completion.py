"""训练归档：报告与知识库一起保存，重复请求复用首次结果。"""
import asyncio
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from ..models.entities import BehaviorReport, ExerciseSession, KbEntry
from ..schemas.dto import SessionFinishIn
from . import ai_client
from .analysis import analysis_summary
from .kb import append_kb_entry


def _completed(db: Session, session: ExerciseSession):
    report = db.query(BehaviorReport).filter_by(session_id=session.id).first()
    if not report:
        return None
    entry = db.query(KbEntry).filter_by(session_id=session.id).first()
    return {
        "session": session,
        "report": report,
        "updated_prescription": None,
        "kb_entry_id": entry.id if entry else None,
        "analysis": analysis_summary(report.cot),
    }


async def complete_session(db: Session, session_id: int, body: SessionFinishIn, *, demo=False):
    session = db.get(ExerciseSession, session_id)
    if not session:
        raise HTTPException(404, "会话不存在")
    previous = _completed(db, session)
    if previous:
        return previous
    if session.status != "running":
        raise HTTPException(409, "当前会话不能结束")

    pose = body.pose_summary or session.pose_summary or {}
    video_path = body.video_path or session.video_path or ""
    payload = {"video_path": video_path, "exercise_name": session.exercise_name}
    # 等待外部服务期间不占用数据库写锁。
    tasks, cot = await asyncio.gather(
        ai_client.behavior_all(payload),
        ai_client.video_cot_evaluate({**payload, "pose_summary": pose, "parsing_summary": {}}),
    )
    if demo:
        tasks = {**tasks, "mode": "mock"}
        cot = {**cot, "mode": "mock"}

    try:
        claimed = db.execute(
            update(ExerciseSession)
            .where(ExerciseSession.id == session_id, ExerciseSession.status == "running")
            .values(status="finishing")
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount == 0:
            db.rollback()
            previous = _completed(db, db.get(ExerciseSession, session_id))
            if previous:
                return previous
            raise HTTPException(409, "训练正在归档，请稍后重试")

        session.status = "finished"
        session.video_path = video_path
        session.pose_summary = pose
        session.finished_at = datetime.utcnow()
        report = BehaviorReport(
            session_id=session.id,
            user_id=session.user_id,
            tasks=tasks.get("tasks", tasks),
            cot=cot,
            video_understanding={"behavior_mode": tasks.get("mode", "unknown")},
        )
        db.add(report)
        db.flush()
        append_kb_entry(db, session=session, report=report, new_presc=None)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _completed(db, session)
