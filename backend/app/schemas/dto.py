from pydantic import BaseModel, Field
from typing import Any, Literal


class LoginIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    privacy_consent: bool = False
    role: Literal["user"] = "user"


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
    age_group: Literal["youth", "middle_age", "elder"] = "middle_age"
    height_cm: float = Field(default=170.0, gt=0, le=300, allow_inf_nan=False)
    weight_kg: float = Field(default=65.0, gt=0, le=700, allow_inf_nan=False)
    chronic_tags: list[str] = Field(default_factory=list)
    goal: Literal["fitness", "medical"] = "fitness"
    scale_id: str = ""
    scores: dict[str, float] = Field(default_factory=dict)
    pose_baseline: dict[str, Any] = Field(default_factory=dict)
    privacy_consent: bool = False
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
    video_path: str = ""
    pose_summary: dict[str, Any] = Field(default_factory=dict)


class SessionFinishIn(BaseModel):
    video_path: str = ""
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
