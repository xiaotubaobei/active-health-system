from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.entities import FitnessAssessment, User, Prescription
from ..schemas.dto import FitnessAssessIn
from ..services.catalog import load_fitness_scales
from ..services.fitness import evaluate_scores
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
    scale, total_score, level = evaluate_scores(body.scale_id, body.scores)
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
