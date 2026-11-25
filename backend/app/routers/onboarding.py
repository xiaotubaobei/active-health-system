from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import get_current_user, owned_user, require_owner
from ..models.entities import FitnessBaseline, Prescription, User
from ..schemas.dto import OnboardingCompleteIn
from ..services.fitness import evaluate_scores, require_age_scale, save_assessment
from ..services.prescription import NoMatchingTemplate, pick_template
from ..services.prescription_review import lock_owner, supersede_pending

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/status")
def status(user_id: int, user: User = Depends(owned_user), db: Session = Depends(get_db)):
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
def complete(body: OnboardingCompleteIn, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = require_owner(body.user_id, actor)
    lock_owner(db, user.id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if not body.privacy_consent:
        raise HTTPException(400, "须同意隐私政策与运动健康免责声明")
    if user.onboarding_done:
        raise HTTPException(409, "基本档案已建立，请到用户档案修改资料，或到体适能评估页补录测评")
    assessment_values = None
    if body.scale_id or body.scores:
        assessment_values = evaluate_scores(body.scale_id, body.scores)
        require_age_scale(body.age_group, assessment_values[0]["id"])
    elif body.pose_baseline:
        raise HTTPException(422, "没有体测项目分数时不保存测评基线，请通过训练记录保存姿态数据")

    user.age_group = body.age_group
    user.height_cm = body.height_cm
    user.weight_kg = body.weight_kg
    user.chronic_tags = body.chronic_tags
    user.goal = body.goal
    user.privacy_consent = True

    baseline = None
    if assessment_values:
        _, baseline = save_assessment(db, user, assessment_values[0], body.scores,
                                      assessment_values[1], assessment_values[2], body.pose_baseline)

    prescription = None
    prescription_message = "基本档案已保存。可在方案页查看模板是否匹配；需要体测换算分时再补录，不要估填。"
    if body.generate_prescription:
        try:
            _, payload = pick_template(user.age_group, user.goal, user.chronic_tags or [])
        except NoMatchingTemplate as error:
            prescription_message = str(error)
        else:
            prescription = Prescription(
                user_id=user.id,
                version=1,
                status="pre_prescription",
                **payload,
                notes="按已填写年龄组、目标及标签匹配的模板草案，未按测评分数制定运动量，需结合活动限制等资料人工核对。",
            )
    if prescription:
        supersede_pending(db, user.id)
        last = (
            db.query(Prescription)
            .filter(Prescription.user_id == user.id)
            .order_by(Prescription.version.desc())
            .first()
        )
        prescription.version = (last.version + 1) if last else 1
        db.add(prescription)
        prescription_message = "已保存模板草案，仅供查看和送审，不代表已按个人体测结果制定运动量。"

    user.onboarding_done = True
    db.commit()
    db.refresh(user)
    if baseline:
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
        "prescription_message": prescription_message,
        "disclaimer": "本系统提供运动健康建议，不构成医疗诊断或治疗。",
    }
