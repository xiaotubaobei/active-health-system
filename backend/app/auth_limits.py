"""Database-backed fixed windows, shared by workers; no raw names/IPs stored."""
import hashlib
import json
import math
from datetime import datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models.entities import AuthRateLimit

WINDOW_SECONDS = 60


def _now():
    return datetime.utcnow()


def _key(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()


def reserve_attempt(db: Session, request: Request, scope: str, identity: str) -> list[str]:
    # Uvicorn's trusted-proxy configuration owns request.client. Never parse XFF here.
    host = request.client.host if request.client else "unknown"
    buckets = [(_key(scope, "source", host), 60),
               (_key(scope, "account", identity), 20),
               (_key(scope, "pair", host, identity), 5)]
    now = _now()
    db.query(AuthRateLimit).filter(AuthRateLimit.expires_at <= now).delete(synchronize_session=False)
    for key, limit in buckets:
        # A savepoint handles simultaneous first attempts without undoing other buckets.
        try:
            with db.begin_nested():
                db.add(AuthRateLimit(key=key, attempts=0,
                                     expires_at=now + timedelta(seconds=WINDOW_SECONDS)))
                db.flush()
        except IntegrityError:
            pass
        changed = db.execute(update(AuthRateLimit).where(
            AuthRateLimit.key == key, AuthRateLimit.attempts < limit,
        ).values(attempts=AuthRateLimit.attempts + 1)).rowcount
        if not changed:
            expiry = db.get(AuthRateLimit, key).expires_at
            retry = max(1, math.ceil((expiry - now).total_seconds()))
            db.commit()
            raise HTTPException(429, f"尝试过于频繁，请在 {retry} 秒后重试。",
                                headers={"Retry-After": str(retry)})
    db.commit()
    # A correct password clears only this source/account pair. Aggregate budgets stay.
    return [buckets[-1][0]]


def clear_attempts(db: Session, keys: list[str]):
    db.query(AuthRateLimit).filter(AuthRateLimit.key.in_(keys)).delete(synchronize_session=False)
