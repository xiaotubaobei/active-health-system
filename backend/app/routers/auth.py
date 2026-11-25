from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy import update
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.entities import AuthSession, User
from ..schemas.dto import LoginIn, RegisterIn, PasswordChangeIn, UserUpdate
from .. import config
from ..passwords import hash_password, verify_password
from ..auth_limits import reserve_attempt, clear_attempts
from ..security import COOKIE_NAME, RESERVED_NAMES, get_current_user, issue_session, owned_user, require_owner, request_token, token_digest

router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])

# Missing/disabled accounts still perform one password hash comparison.
_DUMMY_PASSWORD = hash_password("unusable-dummy-password-for-timing")


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
    demos = [("demo", "user")]
    for name, role in demos:
        u = db.query(User).filter(User.username == name).first()
        if not u:
            db.add(
                User(
                    username=name,
                    password=hash_password("123456"),
                    role=role,
                    privacy_consent=True,
                    onboarding_done=True,
                )
            )
        else:
            u.role = "user"
            # 演示账号默认已完成引导，避免卡住旧库
            if not u.onboarding_done and name == "demo":
                u.privacy_consent = True
                u.onboarding_done = True
    db.commit()


@router.post("/register")
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    if not body.privacy_consent:
        raise HTTPException(400, "请先勾选隐私同意与医疗免责声明")
    name = (body.username or "").strip()
    if len(name) < 2:
        raise HTTPException(400, "用户名至少 2 个字符")
    if name.casefold() in RESERVED_NAMES:
        raise HTTPException(400, "该用户名为系统保留名称，请使用其他名称")
    if db.query(User).filter(User.username == name).first():
        raise HTTPException(400, "用户名已存在")
    user = User(
        username=name,
        password=hash_password(body.password),
        role="user",
        privacy_consent=True,
        onboarding_done=False,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "用户名已存在")
    return {
        "token": issue_session(db, user, response, request),
        "user": _user_public(user),
    }


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    name = body.username.strip()
    keys = reserve_attempt(db, request, "login", name)
    if name in RESERVED_NAMES:
        if not config.ENABLE_DEMO_ACCOUNTS or name != "demo":
            verify_password(body.password, _DUMMY_PASSWORD)
            raise HTTPException(401, "演示账号未启用，请注册或使用个人账号")
        _ensure_demo_users(db)
    user = db.query(User).filter(User.username == name).first()
    correct = verify_password(body.password, user.password if user else _DUMMY_PASSWORD)
    if not user or not correct:
        raise HTTPException(401, "用户名或密码错误")
    clear_attempts(db, keys)
    return {
        "token": issue_session(db, user, response, request),
        "user": _user_public(user),
    }


@router.post("/change-password")
def change_password(body: PasswordChangeIn, request: Request, response: Response,
                    actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if actor.username in RESERVED_NAMES:
        raise HTTPException(403, "演示账号不支持修改密码，请注册个人账号。")
    keys = reserve_attempt(db, request, "password-change", str(actor.id))
    old_hash = actor.password
    if not verify_password(body.current_password, old_hash):
        # A wrong current password is a form error, not an expired login.
        raise HTTPException(400, "当前密码不正确，请重新输入。")
    if body.current_password == body.new_password:
        raise HTTPException(400, "新密码不能与当前密码相同。")
    new_hash = hash_password(body.new_password)
    changed = db.execute(update(User).where(User.id == actor.id, User.password == old_hash)
                         .values(password=new_hash).execution_options(synchronize_session=False)).rowcount
    if not changed:
        db.rollback()
        raise HTTPException(409, "密码已在其他页面修改，请重新登录后再试。")
    db.query(AuthSession).filter_by(user_id=actor.id).delete(synchronize_session=False)
    clear_attempts(db, keys)
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/", secure=config.COOKIE_SECURE, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True, "reauthenticate": True}


@router.post("/logout")
def logout(request: Request, response: Response, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(AuthSession).filter_by(token_hash=token_digest(request_token(request))).delete()
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/", secure=config.COOKIE_SECURE, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True}


@users_router.get("/me")
def me(user_id: int | None = None, user: User = Depends(get_current_user)):
    if user_id is not None:
        require_owner(user_id, user)
    return _user_public(user)


@users_router.put("/me")
def update_me(body: UserUpdate, user_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user_id is not None:
        require_owner(user_id, user)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return _user_public(user)


@users_router.get("/{user_id}/export")
def export_user_data(user_id: int, user: User = Depends(owned_user), db: Session = Depends(get_db)):
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
