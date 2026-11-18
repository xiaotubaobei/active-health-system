"""处方审核权限、固定快照及同一用户处方操作的事务串行化。"""
from datetime import datetime

from sqlalchemy import update

from ..models.entities import PrescriptionReview, User

REVIEW_ROLES = {"physician", "prescription_specialist"}
VISIBLE_REVIEW_STATUSES = {"pending", "approved", "rejected"}


def can_review(role, library):
    return role == "physician" or (role == "prescription_specialist" and library == "fitness")


def lock_owner(db, user_id):
    # 在读处方/申请之前取得写锁；生成、送审、撤回和决定共用此锁。
    db.execute(update(User).where(User.id == user_id).values(id=User.id))
    db.refresh(db.get(User, user_id))


def snapshot(row):
    fields = ("id", "version", "library", "template_id", "status", "mode", "intensity",
              "frequency", "duration", "cycle", "volume", "progression", "exercises",
              "health_plan", "notes")
    return {key: getattr(row, key) for key in fields}


def supersede_pending(db, user_id):
    db.query(PrescriptionReview).filter_by(user_id=user_id, status="pending").update({
        "status": "superseded", "pending_prescription_id": None,
        "decision_note": "用户生成了新版处方，本次申请自动失效", "decided_at": datetime.utcnow(),
    }, synchronize_session=False)
