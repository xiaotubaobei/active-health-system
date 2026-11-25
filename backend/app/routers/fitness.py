from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..security import get_current_user, require_owner
from ..models.entities import User, Prescription
from ..schemas.dto import FitnessAssessIn
from ..services.catalog import load_fitness_scales
from ..services.fitness import evaluate_scores, require_age_scale, save_assessment
from ..services.prescription import next_status
from ..services.prescription_review import lock_owner

router = APIRouter(prefix="/fitness", tags=["fitness"])


@router.get("/scales")
def scales():
    return load_fitness_scales()


@router.post("/assess")
def assess(body: FitnessAssessIn, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = require_owner(body.user_id, actor)
    lock_owner(db, user.id)
    scale, total_score, level = evaluate_scores(body.scale_id, body.scores)
    require_age_scale(user.age_group, scale["id"])
    if not user.onboarding_done:
        raise HTTPException(409, "请先填写基本档案，再录入本人测评")
    row, _ = save_assessment(db, user, scale, body.scores, total_score, level)
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
