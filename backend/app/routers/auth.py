from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.entities import User
from ..schemas.dto import LoginIn, RegisterIn, UserUpdate

router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])


def _user_public(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "age_group": user.age_group,
        "height_cm": user.height_cm,
        "weight_kg": user.weight_kg,
        "chronic_tags": user.chronic_tags or [],
        "goal": user.goal,
        "privacy_consent": bool(user.privacy_consent),
        "onboarding_done": bool(user.onboarding_done),
    }


def _ensure_demo_users(db: Session):
    demos = [
        ("demo", "user"),
        ("specialist", "prescription_specialist"),
        ("physician", "physician"),
        ("admin", "admin"),
    ]
    for name, role in demos:
        u = db.query(User).filter(User.username == name).first()
        if not u:
            db.add(
                User(
                    username=name,
                    password="123456",
                    role=role,
                    privacy_consent=True,
                    onboarding_done=True,
                )
            )
        else:
            # 演示账号默认已完成引导，避免卡住旧库
            if not u.onboarding_done and name == "demo":
                u.privacy_consent = True
                u.onboarding_done = True
    db.commit()


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if not body.privacy_consent:
        raise HTTPException(400, "请先勾选隐私同意与医疗免责声明")
    name = (body.username or "").strip()
    if len(name) < 2:
        raise HTTPException(400, "用户名至少 2 个字符")
    if db.query(User).filter(User.username == name).first():
        raise HTTPException(400, "用户名已存在")
    role = body.role if body.role in ("user", "prescription_specialist", "physician") else "user"
    user = User(
        username=name,
        password=body.password or "123456",
        role=role,
        privacy_consent=True,
        onboarding_done=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "token": f"dev-{user.id}-{user.role}",
        "user": _user_public(user),
    }


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    _ensure_demo_users(db)
    user = db.query(User).filter(User.username == body.username).first()
    if not user or user.password != body.password:
        raise HTTPException(401, "用户名或密码错误")
    return {
        "token": f"dev-{user.id}-{user.role}",
        "user": _user_public(user),
    }


@users_router.get("/me")
def me(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    return _user_public(user)


@users_router.put("/me")
def update_me(user_id: int, body: UserUpdate, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return _user_public(user)


@users_router.get("/{user_id}/export")
def export_user_data(user_id: int, db: Session = Depends(get_db)):
    """导出某用户数据（本人可见范围）。"""
    from ..models.entities import (
        BehaviorReport,
        CoachEvent,
        ExerciseSession,
        FitnessAssessment,
        FitnessBaseline,
        KbEntry,
        Prescription,
    )

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    return {
        "user": _user_public(user),
        "baselines": [
            {
                "id": b.id,
                "total_score": b.total_score,
                "level": b.level,
                "scores": b.scores,
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b in db.query(FitnessBaseline).filter(FitnessBaseline.user_id == user_id).all()
        ],
        "assessments": db.query(FitnessAssessment).filter(FitnessAssessment.user_id == user_id).count(),
        "prescriptions": db.query(Prescription).filter(Prescription.user_id == user_id).count(),
        "sessions": db.query(ExerciseSession).filter(ExerciseSession.user_id == user_id).count(),
        "reports": db.query(BehaviorReport).filter(BehaviorReport.user_id == user_id).count(),
        "coach_events": db.query(CoachEvent).filter(CoachEvent.user_id == user_id).count(),
        "kb_entries": db.query(KbEntry).filter(KbEntry.user_id == user_id).count(),
    }
