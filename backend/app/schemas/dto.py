from pydantic import BaseModel, Field, model_validator
from typing import Any, Literal


class LoginIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    privacy_consent: bool = False
    role: Literal["user"] = "user"


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    age_group: Literal["youth", "middle_age", "elder"] | None = None
    height_cm: float | None = Field(default=None, gt=0, le=300, allow_inf_nan=False)
    weight_kg: float | None = Field(default=None, gt=0, le=700, allow_inf_nan=False)
    chronic_tags: list[str] | None = None
    goal: Literal["fitness", "medical"] | None = None
    privacy_consent: bool | None = None


class FitnessAssessIn(BaseModel):
    user_id: int
    scale_id: str
    scores: dict[str, float] = Field(default_factory=dict)


class OnboardingCompleteIn(BaseModel):
    user_id: int
    age_group: Literal["youth", "middle_age", "elder"]
    height_cm: float = Field(gt=0, le=300, allow_inf_nan=False)
    weight_kg: float = Field(gt=0, le=700, allow_inf_nan=False)
    chronic_tags: list[str] = Field(default_factory=list)
    goal: Literal["fitness", "medical"]
    scale_id: str = ""
    scores: dict[str, float] = Field(default_factory=dict)
    pose_baseline: dict[str, Any] = Field(default_factory=dict)
    privacy_consent: bool = False
    generate_prescription: bool = True


class BodyParseIn(BaseModel):
    user_id: int
    image_path: str = ""
    clicks: list[dict] = Field(default_factory=list)
    waist_cm: float | None = Field(default=None, gt=0, le=300, allow_inf_nan=False)
    hip_cm: float | None = Field(default=None, gt=0, le=300, allow_inf_nan=False)
    body_fat: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)


class PrescriptionGenerateIn(BaseModel):
    user_id: int


class PrescriptionReviewIn(BaseModel):
    reviewer_username: str = Field(min_length=2, max_length=64)
    consent: bool = False
    request_note: str = Field(default="", max_length=2000)


class PrescriptionDecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(min_length=1, max_length=2000)


class SessionStartIn(BaseModel):
    start_key: str | None = Field(default=None, min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    user_id: int
    exercise_id: str
    exercise_name: str = ""
    prescription_id: int = 0
    video_path: str = ""
    pose_summary: dict[str, Any] = Field(default_factory=dict)


class SessionFinishIn(BaseModel):
    expected_revision: int | None = Field(default=None, ge=0)
    video_path: str = ""
    pose_summary: dict[str, Any] = Field(default_factory=dict)


class SessionFeedbackIn(BaseModel):
    expected_revision: int = Field(ge=0, strict=True)
    performed: bool = Field(strict=True)
    completion: Literal["completed", "partial", "stopped"] | None = None
    effort: Literal["easy", "moderate", "hard"] | None = None
    discomfort: bool | None = Field(default=None, strict=True)
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def validate_participation(self):
        answers = (self.completion, self.effort, self.discomfort)
        if self.performed and any(answer is None for answer in answers):
            raise ValueError("实际训练请填写完成情况、费力程度和不适情况")
        if not self.performed and any(answer is not None for answer in answers):
            raise ValueError("仅体验样本时不记录本人的训练完成情况或感受")
        self.note = self.note.strip()
        return self


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
