from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..security import get_current_user, owned_user, require_owner
from ..models.entities import Prescription, User
from ..schemas.dto import PrescriptionGenerateIn
from ..services.catalog import load_prescription_libs
from ..services.prescription import pick_template, next_status, STATUS_FLOW

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])


@router.get("/templates")
def templates():
    return load_prescription_libs()


@router.get("/status_flow")
def status_flow():
    return STATUS_FLOW


@router.post("/generate")
def generate(body: PrescriptionGenerateIn, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = require_owner(body.user_id, actor)
    last = (
        db.query(Prescription)
        .filter(Prescription.user_id == user.id)
        .order_by(Prescription.version.desc())
        .first()
    )
    version = (last.version + 1) if last else 1
    library, payload = pick_template(user.age_group, user.goal, user.chronic_tags or [])
    row = Prescription(
        user_id=user.id,
        version=version,
        status="pre_prescription",
        **payload,
        notes="由规则引擎自动生成（框架版）",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/current")
def current(user_id: int, user: User = Depends(owned_user), db: Session = Depends(get_db)):
    row = (
        db.query(Prescription)
        .filter(Prescription.user_id == user_id)
        .order_by(Prescription.version.desc())
        .first()
    )
    if not row:
        raise HTTPException(404, "尚无处方，请先生成")
    return row


@router.get("/history")
def history(user_id: int, user: User = Depends(owned_user), db: Session = Depends(get_db)):
    return (
        db.query(Prescription)
        .filter(Prescription.user_id == user_id)
        .order_by(Prescription.version.desc())
        .all()
    )


@router.post("/{presc_id}/advance")
def advance(presc_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(Prescription, presc_id)
    if not row or row.user_id != actor.id:
        raise HTTPException(404, "处方不存在")
    if actor.role not in {"prescription_specialist", "physician", "admin"}:
        raise HTTPException(403, "处方状态需由授权人员审核后推进")
    row.status = next_status(row.status)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row
