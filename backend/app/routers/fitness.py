from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.entities import FitnessAssessment, User, Prescription
from ..schemas.dto import FitnessAssessIn
from ..services.catalog import load_fitness_scales
from ..services.prescription import next_status

router = APIRouter(prefix="/fitness", tags=["fitness"])


@router.get("/scales")
def scales():
    return load_fitness_scales()


@router.post("/assess")
def assess(body: FitnessAssessIn, db: Session = Depends(get_db)):
    user = db.get(User, body.user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
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
    level = "excellent" if total_score >= 85 else "good" if total_score >= 70 else "average" if total_score >= 55 else "poor"
    row = FitnessAssessment(
        user_id=user.id,
        scale_id=scale["id"],
        scores=body.scores,
        total_score=total_score,
        level=level,
    )
    db.add(row)
    # advance latest prescription if any
    presc = (
        db.query(Prescription)
        .filter(Prescription.user_id == user.id)
        .order_by(Prescription.version.desc())
        .first()
    )
    if presc and presc.status == "clinical_intake":
        presc.status = next_status(presc.status)
    db.commit()
    db.refresh(row)
    return row
