from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.entities import FitnessAssessment, FitnessBaseline, Prescription, User
from ..schemas.dto import OnboardingCompleteIn
from ..services.fitness import evaluate_scores
from ..services.prescription import pick_template

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/status")
def status(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    baseline = (
        db.query(FitnessBaseline)
        .filter(FitnessBaseline.user_id == user_id)
        .order_by(FitnessBaseline.id.desc())
        .first()
    )
    presc = (
        db.query(Prescription)
        .filter(Prescription.user_id == user_id)
        .order_by(Prescription.version.desc())
        .first()
    )
    return {
        "privacy_consent": bool(user.privacy_consent),
        "onboarding_done": bool(user.onboarding_done),
        "has_baseline": baseline is not None,
        "has_prescription": presc is not None,
        "baseline": baseline,
        "current_prescription_id": presc.id if presc else None,
    }


@router.post("/complete")
def complete(body: OnboardingCompleteIn, db: Session = Depends(get_db)):
    user = db.get(User, body.user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if not body.privacy_consent:
        raise HTTPException(400, "须同意隐私政策与运动健康免责声明")
    if user.onboarding_done:
        raise HTTPException(409, "首次测评已完成，请到体适能评估页进行后续测评")
    scale, total_score, level = evaluate_scores(body.scale_id, body.scores)
    expected_scale = "youth" if body.age_group == "youth" else "middle_elder"
    if scale["id"] != expected_scale:
        raise HTTPException(422, "量表与年龄组不匹配")

    user.age_group = body.age_group
    user.height_cm = body.height_cm
    user.weight_kg = body.weight_kg
    user.chronic_tags = body.chronic_tags
    user.goal = body.goal
    user.privacy_consent = True

    assess = FitnessAssessment(
        user_id=user.id,
        scale_id=scale["id"],
        scores=body.scores,
        total_score=total_score,
        level=level,
    )
    db.add(assess)
    db.flush()

    baseline = FitnessBaseline(
        user_id=user.id,
        assessment_id=assess.id,
        scores=body.scores,
        total_score=total_score,
        level=level,
        pose_baseline=body.pose_baseline or {},
        profile_snapshot={
            "age_group": user.age_group,
            "height_cm": user.height_cm,
            "weight_kg": user.weight_kg,
            "goal": user.goal,
            "chronic_tags": user.chronic_tags or [],
        },
    )
    db.add(baseline)

    prescription = None
    if body.generate_prescription:
        last = (
            db.query(Prescription)
            .filter(Prescription.user_id == user.id)
            .order_by(Prescription.version.desc())
            .first()
        )
        version = (last.version + 1) if last else 1
        library, payload = pick_template(user.age_group, user.goal, user.chronic_tags or [])
        prescription = Prescription(
            user_id=user.id,
            version=version,
            status="pre_prescription",
            **payload,
            notes="入门引导后自动生成首份处方（运动健康建议，非诊疗）",
        )
        db.add(prescription)

    user.onboarding_done = True
    db.commit()
    db.refresh(user)
    db.refresh(baseline)
    if prescription:
        db.refresh(prescription)

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "age_group": user.age_group,
            "height_cm": user.height_cm,
            "weight_kg": user.weight_kg,
            "chronic_tags": user.chronic_tags or [],
            "goal": user.goal,
            "privacy_consent": True,
            "onboarding_done": True,
        },
        "baseline": baseline,
        "prescription": prescription,
        "disclaimer": "本系统提供运动健康建议，不构成医疗诊断或治疗。",
    }
