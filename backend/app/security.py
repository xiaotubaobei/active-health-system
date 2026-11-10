"""Server-side login sessions shared by all private API routes."""
import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from . import config
from .database import get_db
from .models.entities import AuthSession, User

COOKIE_NAME = "ah_session"
SESSION_SECONDS = 8 * 60 * 60
RESERVED_NAMES = {"demo", "specialist", "physician", "admin"}


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def request_token(request: Request) -> str:
    authorization = request.headers.get("authorization")
    if authorization is not None:
        scheme, _, token = authorization.partition(" ")
        return token if scheme.lower() == "bearer" else ""
    return request.cookies.get(COOKIE_NAME, "")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request_token(request)
    session = db.get(AuthSession, token_digest(token)) if token else None
    if not session or session.expires_at <= datetime.utcnow():
        raise HTTPException(401, "登录已失效，请重新登录", headers={"WWW-Authenticate": "Bearer"})
    user = db.get(User, session.user_id)
    if not user or (user.username in RESERVED_NAMES and not (config.ENABLE_DEMO_ACCOUNTS and user.username == "demo")):
        raise HTTPException(401, "账号不可用，请使用个人账号登录")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and not request.headers.get("authorization"):
        if request.headers.get("x-requested-with") != "ActiveHealth":
            raise HTTPException(403, "请求来源校验失败")
    return user


def require_owner(user_id: int, actor: User) -> User:
    if user_id != actor.id:
        raise HTTPException(404, "数据不存在或无权访问")
    return actor


def owned_user(user_id: int, actor: User = Depends(get_current_user)) -> User:
    return require_owner(user_id, actor)


def issue_session(db: Session, user: User, response: Response, request: Request) -> str:
    # Signing in replaces the browser's previous session; other devices are unchanged.
    previous = request_token(request)
    if previous:
        db.query(AuthSession).filter_by(token_hash=token_digest(previous)).delete()
    db.query(AuthSession).filter(AuthSession.expires_at <= datetime.utcnow()).delete()
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=token_digest(token), user_id=user.id,
                       expires_at=datetime.utcnow() + timedelta(seconds=SESSION_SECONDS)))
    db.commit()
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=config.COOKIE_SECURE, samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return token
