from datetime import datetime
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32), default="user")  # user|prescription_specialist|physician|admin
    age_group: Mapped[str] = mapped_column(String(32), default="middle_age")
    height_cm: Mapped[float] = mapped_column(Float, default=170.0)
    weight_kg: Mapped[float] = mapped_column(Float, default=65.0)
    chronic_tags: Mapped[dict] = mapped_column(JSON, default=list)
    goal: Mapped[str] = mapped_column(String(32), default="fitness")  # fitness|medical
    privacy_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class FitnessAssessment(Base):
    __tablename__ = "fitness_assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    scale_id: Mapped[str] = mapped_column(String(64))
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    level: Mapped[str] = mapped_column(String(32), default="average")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FitnessBaseline(Base):
    """入门测评沉淀的基线画像（每人可多条，最新有效）。"""
    __tablename__ = "fitness_baselines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assessment_id: Mapped[int] = mapped_column(Integer, default=0)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    level: Mapped[str] = mapped_column(String(32), default="average")
    pose_baseline: Mapped[dict] = mapped_column(JSON, default=dict)
    profile_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BodyMetrics(Base):
    __tablename__ = "body_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bmi: Mapped[float] = mapped_column(Float, default=0.0)
    whr: Mapped[float] = mapped_column(Float, default=0.0)
    body_fat: Mapped[float] = mapped_column(Float, default=0.0)
    parsing_result: Mapped[dict] = mapped_column(JSON, default=dict)
    image_path: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Prescription(Base):
    __tablename__ = "prescriptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    library: Mapped[str] = mapped_column(String(32), default="fitness")
    template_id: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(64), default="clinical_intake")
    mode: Mapped[str] = mapped_column(String(64), default="")
    intensity: Mapped[str] = mapped_column(String(64), default="")
    frequency: Mapped[str] = mapped_column(String(64), default="")
    duration: Mapped[str] = mapped_column(String(64), default="")
    cycle: Mapped[str] = mapped_column(String(64), default="")
    volume: Mapped[str] = mapped_column(String(64), default="")
    progression: Mapped[str] = mapped_column(String(128), default="")
    exercises: Mapped[dict] = mapped_column(JSON, default=list)
    health_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExerciseSession(Base):
    __tablename__ = "exercise_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    prescription_id: Mapped[int] = mapped_column(Integer, default=0)
    exercise_id: Mapped[str] = mapped_column(String(64))
    exercise_name: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(32), default="running")
    video_path: Mapped[str] = mapped_column(String(512), default="")
    pose_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BehaviorReport(Base):
    __tablename__ = "behavior_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("exercise_sessions.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    tasks: Mapped[dict] = mapped_column(JSON, default=dict)
    cot: Mapped[dict] = mapped_column(JSON, default=dict)
    video_understanding: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CoachEvent(Base):
    """运动中实时交互事件（链路 A）。"""
    __tablename__ = "coach_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("exercise_sessions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    level: Mapped[str] = mapped_column(String(16), default="info")  # info|warn
    code: Mapped[str] = mapped_column(String(64), default="")
    text: Mapped[str] = mapped_column(String(512), default="")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KbEntry(Base):
    """个人运动知识库条目：每次运动结束追加一条。"""
    __tablename__ = "kb_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    prescription_id: Mapped[int] = mapped_column(Integer, default=0)
    prescription_version: Mapped[int] = mapped_column(Integer, default=0)
    exercise_id: Mapped[str] = mapped_column(String(64), default="")
    exercise_name: Mapped[str] = mapped_column(String(128), default="")
    pose_digest: Mapped[dict] = mapped_column(JSON, default=dict)
    coach_digest: Mapped[dict] = mapped_column(JSON, default=dict)
    multimodal: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    errors: Mapped[dict] = mapped_column(JSON, default=list)
    advice: Mapped[str] = mapped_column(Text, default="")
    history_note: Mapped[str] = mapped_column(String(512), default="")
    prescription_changed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DeviceReading(Base):
    __tablename__ = "device_readings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    device_type: Mapped[str] = mapped_column(String(32), default="bracelet")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
