from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.entities import ExerciseSession, BehaviorReport, Prescription, User
from ..schemas.dto import SessionStartIn, SessionFinishIn
from ..services import ai_client
from ..services.prescription import adjust_by_report

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/start")
async def start(body: SessionStartIn, db: Session = Depends(get_db)):
    user = db.get(User, body.user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
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
    session = db.get(ExerciseSession, session_id)
    if not session:
        raise HTTPException(404, "会话不存在")
    session.status = "finished"
    session.video_path = body.video_path
    if body.pose_summary:
        session.pose_summary = body.pose_summary
    session.finished_at = datetime.utcnow()

    tasks = await ai_client.behavior_all(
        {
            "video_path": session.video_path,
            "exercise_name": session.exercise_name,
        }
    )
    cot = await ai_client.video_cot_evaluate(
        {
            "video_path": session.video_path,
            "exercise_name": session.exercise_name,
            "pose_summary": session.pose_summary or {},
            "parsing_summary": {},
        }
    )
    report = BehaviorReport(
        session_id=session.id,
        user_id=session.user_id,
        tasks=tasks.get("tasks", tasks),
        cot=cot,
    )
    db.add(report)

    # closed-loop prescription adjustment
    presc = None
    if session.prescription_id:
        presc = db.get(Prescription, session.prescription_id)
    if not presc:
        presc = (
            db.query(Prescription)
            .filter(Prescription.user_id == session.user_id)
            .order_by(Prescription.version.desc())
            .first()
        )
    new_presc = None
    if presc:
        score = float(cot.get("score", 75))
        errors = list(cot.get("errors") or [])
        new_exercises, note = adjust_by_report(presc.exercises or [], score, errors)
        new_presc = Prescription(
            user_id=presc.user_id,
            version=presc.version + 1,
            library=presc.library,
            template_id=presc.template_id,
            status="feedback",
            mode=presc.mode,
            intensity=presc.intensity,
            frequency=presc.frequency,
            duration=presc.duration,
            cycle=presc.cycle,
            volume=presc.volume,
            progression=presc.progression,
            exercises=new_exercises,
            health_plan=presc.health_plan or {},
            notes=f"由运动后CoT自动微调：{note}",
        )
        db.add(new_presc)

    db.commit()
    db.refresh(session)
    db.refresh(report)
    if new_presc:
        db.refresh(new_presc)
    return {"session": session, "report": report, "updated_prescription": new_presc}
