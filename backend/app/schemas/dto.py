from pydantic import BaseModel, Field
from typing import Any


class LoginIn(BaseModel):
    username: str
    password: str = "123456"


class RegisterIn(BaseModel):
    username: str
    password: str = "123456"
    privacy_consent: bool = False
    role: str = "user"


class UserUpdate(BaseModel):
    age_group: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    chronic_tags: list[str] | None = None
    goal: str | None = None
    privacy_consent: bool | None = None


class FitnessAssessIn(BaseModel):
    user_id: int
    scale_id: str
    scores: dict[str, float] = Field(default_factory=dict)


class OnboardingCompleteIn(BaseModel):
    user_id: int
    age_group: str = "middle_age"
    height_cm: float = 170.0
    weight_kg: float = 65.0
    chronic_tags: list[str] = Field(default_factory=list)
    goal: str = "fitness"
    scale_id: str = ""
    scores: dict[str, float] = Field(default_factory=dict)
    pose_baseline: dict[str, Any] = Field(default_factory=dict)
    privacy_consent: bool = True
    generate_prescription: bool = True


class BodyParseIn(BaseModel):
    user_id: int
    image_path: str = ""
    clicks: list[dict] = Field(default_factory=list)
    waist_cm: float | None = None
    hip_cm: float | None = None
    body_fat: float | None = None


class PrescriptionGenerateIn(BaseModel):
    user_id: int


class SessionStartIn(BaseModel):
    user_id: int
    exercise_id: str
    exercise_name: str = ""
    prescription_id: int = 0


class SessionFinishIn(BaseModel):
    video_path: str = "uploads/mock_session.mp4"
    pose_summary: dict[str, Any] = Field(default_factory=dict)


class VideoPoseInferIn(BaseModel):
    video_path: str
    sample_hz: float = Field(default=6.0, ge=1.0, le=15.0)
    exercise_id: str | None = None


class DeviceReadingIn(BaseModel):
    user_id: int
    device_type: str = "bracelet"
    payload: dict[str, Any] = Field(default_factory=dict)


class CoachTickIn(BaseModel):
    session_id: int
    user_id: int
    exercise_id: str = "squat"
    knee_l: float | None = None
    knee_r: float | None = None
    trunk_lean: float | None = None


class CoachEventIn(BaseModel):
    session_id: int
    user_id: int
    level: str = "info"
    code: str = ""
    text: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
