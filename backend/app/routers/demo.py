"""一键演示闭环，方便给导师交差。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.entities import User, FitnessAssessment, Prescription, ExerciseSession, BehaviorReport
from ..services.prescription import pick_template, adjust_by_report
from ..services import ai_client
from datetime import datetime

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoLoopIn(BaseModel):
    user_id: int
    exercise_id: str = "squat"
    exercise_name: str = "深蹲"


@router.post("/run-loop")
async def run_loop(body: DemoLoopIn, db: Session = Depends(get_db)):
    user = db.get(User, body.user_id)
    if not user:
        raise HTTPException(404, "用户不存在")

    scores = {
        "bmi": 78,
        "strength": 72,
        "flexibility": 68,
        "balance": 70,
        "coordination": 74,
        "daily_activity": 76,
        "vital_capacity": 80,
        "run_50": 75,
        "sit_reach": 70,
        "skip_1min": 82,
    }
    assess = FitnessAssessment(
        user_id=user.id,
        scale_id="middle_elder" if user.age_group != "youth" else "youth",
        scores=scores,
        total_score=73.5,
        level="good",
    )
    db.add(assess)

    library, payload = pick_template(user.age_group, user.goal, user.chronic_tags or [])
    last = (
        db.query(Prescription)
        .filter(Prescription.user_id == user.id)
        .order_by(Prescription.version.desc())
        .first()
    )
    version = (last.version + 1) if last else 1
    presc = Prescription(
        user_id=user.id,
        version=version,
        status="implementing",
        **payload,
        notes="演示剧本自动生成",
    )
    db.add(presc)
    db.flush()

    pose = await ai_client.pose_infer({"exercise_id": body.exercise_id})
    session = ExerciseSession(
        user_id=user.id,
        prescription_id=presc.id,
        exercise_id=body.exercise_id,
        exercise_name=body.exercise_name,
        status="finished",
        video_path="uploads/demo_loop.mp4",
        pose_summary=pose,
        finished_at=datetime.utcnow(),
    )
    db.add(session)
    db.flush()

    tasks = await ai_client.behavior_all(
        {"video_path": session.video_path, "exercise_name": session.exercise_name}
    )
    cot = await ai_client.video_cot_evaluate(
        {
            "video_path": session.video_path,
            "exercise_name": session.exercise_name,
            "pose_summary": pose,
            "parsing_summary": {},
        }
    )
    report = BehaviorReport(
        session_id=session.id,
        user_id=user.id,
        tasks=tasks.get("tasks", tasks),
        cot=cot,
    )
    db.add(report)

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
        notes=f"演示闭环：{note}",
    )
    db.add(new_presc)
    db.commit()
    db.refresh(session)
    db.refresh(report)
    db.refresh(new_presc)
    return {
        "ok": True,
        "message": "演示闭环完成：体适能 → 处方 → 会话 → CoT 报告 → 处方微调",
        "session_id": session.id,
        "report": report,
        "prescription": new_presc,
    }
