from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.entities import FitnessAssessment, FitnessBaseline, Prescription, User
from ..schemas.dto import OnboardingCompleteIn
from ..services.catalog import load_fitness_scales
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

    user.age_group = body.age_group
    user.height_cm = body.height_cm
    user.weight_kg = body.weight_kg
    user.chronic_tags = body.chronic_tags
    user.goal = body.goal
    user.privacy_consent = True

    scales = {s["id"]: s for s in load_fitness_scales()}
    scale = scales.get(body.scale_id) or next(iter(scales.values()))
    total = 0.0
    weight_sum = 0.0
    for item in scale["items"]:
        w = float(item["weight"])
        score = float(body.scores.get(item["key"], 70))
        total += score * w
        weight_sum += w
    total_score = round(total / weight_sum, 2) if weight_sum else 0
    level = (
        "excellent"
        if total_score >= 85
        else "good"
        if total_score >= 70
        else "average"
        if total_score >= 55
        else "poor"
    )

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
