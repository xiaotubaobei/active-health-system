from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..security import get_current_user, owned_user, require_owner
from ..models.entities import FitnessAssessment, Prescription, PrescriptionReview, User
from ..schemas.dto import PrescriptionGenerateIn, PrescriptionReviewIn, PrescriptionDecisionIn
from ..services.catalog import load_prescription_libs
from ..services.prescription import NoMatchingTemplate, pick_template, template_availability, STATUS_FLOW
from ..services.prescription_review import (
    REVIEW_ROLES, VISIBLE_REVIEW_STATUSES, can_review, lock_owner, snapshot, supersede_pending,
)

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
    lock_owner(db, user.id)
    if not user.onboarding_done:
        raise HTTPException(409, "请先填写基本档案，不能使用注册占位资料生成方案")
    try:
        _, payload = pick_template(user.age_group, user.goal, user.chronic_tags or [])
    except NoMatchingTemplate as error:
        raise HTTPException(422, str(error)) from error
    supersede_pending(db, user.id)
    last = (
        db.query(Prescription)
        .filter(Prescription.user_id == user.id)
        .order_by(Prescription.version.desc())
        .first()
    )
    version = (last.version + 1) if last else 1
    row = Prescription(
        user_id=user.id,
        version=version,
        status="pre_prescription",
        **payload,
        notes="按已填写年龄组、目标及标签匹配的模板草案，未按测评分数制定运动量，需结合活动限制等资料人工核对。",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/availability")
def availability(user_id: int, user: User = Depends(owned_user)):
    if not user.onboarding_done:
        return {"matched": False, "reason": "请先填写基本档案，注册占位资料不能用于匹配方案。",
                "library": None, "template_id": None}
    return template_availability(user.age_group, user.goal, user.chronic_tags or [])


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
    raise HTTPException(409, "请通过指定审核人的人工审核流程处理，不能直接推进状态")


def _latest(db, user_id):
    return db.query(Prescription).filter_by(user_id=user_id).order_by(
        Prescription.version.desc(), Prescription.id.desc()).first()


def _public_review(row):
    return {key: getattr(row, key) for key in (
        "id", "prescription_id", "user_id", "reviewer_id", "requester_name", "reviewer_name",
        "reviewer_role", "status", "prescription_snapshot", "profile_snapshot", "request_note",
        "decision_note", "created_at", "decided_at",
    )}


@router.get("/reviews/mine")
def my_reviews(offset: int = 0, limit: int = 50, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _review_page(db.query(PrescriptionReview).filter_by(user_id=actor.id), offset, limit)


def _review_page(query, offset, limit):
    if offset < 0 or not 1 <= limit <= 100:
        raise HTTPException(422, "分页范围不正确")
    return {"total": query.count(), "items": [_public_review(r) for r in query.order_by(
        PrescriptionReview.id.desc()).offset(offset).limit(limit).all()]}


@router.get("/reviews/inbox")
def review_inbox(status: str = "pending", offset: int = 0, limit: int = 50,
                 actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if actor.role not in REVIEW_ROLES:
        raise HTTPException(403, "需要审核人员权限")
    if status not in VISIBLE_REVIEW_STATUSES:
        raise HTTPException(422, "不支持的审核状态")
    query = db.query(PrescriptionReview).filter_by(reviewer_id=actor.id, status=status)
    if actor.role != "physician":
        # 医师被降为处方师后也不能继续读取医疗申请。
        query = query.join(Prescription).filter(Prescription.library == "fitness")
    return _review_page(query, offset, limit)


@router.post("/{presc_id}/reviews")
def submit_review(presc_id: int, body: PrescriptionReviewIn,
                  actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lock_owner(db, actor.id)
    row = db.get(Prescription, presc_id)
    if not row or row.user_id != actor.id:
        raise HTTPException(404, "处方不存在")
    if not body.consent:
        raise HTTPException(400, "请明确同意向指定审核人提供本次处方、档案和最近测评快照")
    if _latest(db, actor.id).id != row.id or row.status not in {"pre_prescription", "monitoring"}:
        raise HTTPException(409, "只能提交当前版本的预处方或监测中处方")
    if db.query(PrescriptionReview).filter_by(pending_prescription_id=row.id).first():
        raise HTTPException(409, "该版处方已在审核中，请勿重复提交")
    reviewer = db.query(User).filter_by(username=body.reviewer_username.strip()).first()
    if not reviewer or reviewer.id == actor.id or not can_review(reviewer.role, row.library):
        raise HTTPException(400, "审核人不可用：请填写其他已授权审核人的账号，医疗处方需指定医师")
    assessment = db.query(FitnessAssessment).filter_by(user_id=actor.id).order_by(FitnessAssessment.id.desc()).first()
    profile = {key: getattr(actor, key) for key in (
        "age_group", "height_cm", "weight_kg", "goal", "chronic_tags",
    )}
    profile["assessment"] = ({"scale_id": assessment.scale_id, "scores": assessment.scores,
                              "total_score": assessment.total_score, "level": assessment.level,
                              "created_at": assessment.created_at.isoformat()} if assessment else None)
    review = PrescriptionReview(
        prescription_id=row.id, pending_prescription_id=row.id, user_id=actor.id,
        reviewer_id=reviewer.id, requester_name=actor.username, reviewer_name=reviewer.username,
        reviewer_role=reviewer.role, prescription_snapshot=snapshot(row), profile_snapshot=profile,
        request_note=body.request_note.strip(),
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return _public_review(review)


@router.post("/reviews/{review_id}/cancel")
def cancel_review(review_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lock_owner(db, actor.id)
    review = db.get(PrescriptionReview, review_id)
    if not review or review.user_id != actor.id:
        raise HTTPException(404, "审核申请不存在")
    if review.status != "pending":
        raise HTTPException(409, "申请已处理，不能撤回")
    review.status = "cancelled"
    review.pending_prescription_id = None
    review.decision_note = "用户撤回申请"
    review.decided_at = datetime.utcnow()
    db.commit()
    db.refresh(review)
    return _public_review(review)


@router.post("/reviews/{review_id}/decision")
def decide_review(review_id: int, body: PrescriptionDecisionIn,
                  actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if actor.role not in REVIEW_ROLES:
        raise HTTPException(403, "需要审核人员权限")
    review = db.get(PrescriptionReview, review_id)
    if not review or review.reviewer_id != actor.id or review.status not in VISIBLE_REVIEW_STATUSES:
        raise HTTPException(404, "审核申请不存在或已撤回")
    lock_owner(db, review.user_id)
    db.refresh(review)  # 锁定后重读，另一个请求可能已处理/撤回。
    if review.status != "pending":
        raise HTTPException(409, "申请已处理或已失效，请刷新列表")
    row = db.get(Prescription, review.prescription_id)
    if not can_review(actor.role, row.library):
        raise HTTPException(403, "医疗处方需要医师审核")
    if _latest(db, row.user_id).id != row.id or snapshot(row) != review.prescription_snapshot:
        raise HTTPException(409, "处方已变化，请用户重新送审")
    if not body.note.strip():
        raise HTTPException(422, "请填写审核意见")
    review.status = body.decision
    review.pending_prescription_id = None
    review.decision_note = body.note.strip()
    review.decided_at = datetime.utcnow()
    review.reviewer_role = actor.role
    if body.decision == "approved":
        row.status = "formal_prescription"
        row.updated_at = review.decided_at
    db.commit()
    db.refresh(review)
    return _public_review(review)
