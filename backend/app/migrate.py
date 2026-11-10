"""轻量 schema 迁移：create_all + SQLite 缺列补齐。"""
from sqlalchemy import inspect, text, select
from sqlalchemy.orm import Session

from .config import DATABASE_URL
from .database import Base, engine
from .models.entities import User
from .passwords import PREFIX, hash_password


def _sqlite_columns(table: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def _add_col(table: str, col: str, ddl: str) -> None:
    cols = _sqlite_columns(table)
    if col in cols:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


def migrate_schema() -> None:
    Base.metadata.create_all(bind=engine)
    if DATABASE_URL.startswith("sqlite"):
        _migrate_sqlite_columns()
    # Upgrade legacy plaintext credentials without changing the user's password.
    with Session(engine) as db:
        for user in db.scalars(select(User).where(User.password.is_not(None))):
            if not user.password.startswith(PREFIX):
                user.password = hash_password(user.password)
        db.commit()


def _migrate_sqlite_columns() -> None:
    insp = inspect(engine)
    if "users" in insp.get_table_names():
        _add_col("users", "privacy_consent", "privacy_consent BOOLEAN DEFAULT 0")
        _add_col("users", "onboarding_done", "onboarding_done BOOLEAN DEFAULT 0")
    if "behavior_reports" in insp.get_table_names():
        _add_col(
            "behavior_reports",
            "video_understanding",
            "video_understanding JSON",
        )
