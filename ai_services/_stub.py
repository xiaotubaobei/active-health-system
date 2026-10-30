"""Shared FastAPI stub factory for AI microservices (framework mocks)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any


def make_app(name: str, version: str = "0.1.0-mock") -> FastAPI:
    app = FastAPI(title=f"AI-{name}", version=version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"service": name, "status": "ok", "mode": "mock"}

    return app


class PoseInferIn(BaseModel):
    image_b64: str | None = None
    video_path: str | None = None
    exercise_id: str | None = None


class PoseKbIn(BaseModel):
    pose_sequence: list[Any] = Field(default_factory=list)
    skeleton_format: str = "coco17"


class VideoGenIn(BaseModel):
    image_path: str = ""
    pose_sequence: list[Any] = Field(default_factory=list)
    prompt: str = ""


class ParsingIn(BaseModel):
    image_path: str = ""
    clicks: list[dict] = Field(default_factory=list)  # {x,y,label: pos|neg}
    text_prompt: str = "person body parts"


class VisualEncIn(BaseModel):
    video_path: str = ""
    frames: list[str] = Field(default_factory=list)


class BehaviorIn(BaseModel):
    video_path: str = ""
    task: str = "recognize"  # recognize|localize|segment|assess|describe
    exercise_name: str = ""
    text_query: str = ""
    visual_features: dict = Field(default_factory=dict)


class VideoCotIn(BaseModel):
    video_path: str = ""
    exercise_name: str = ""
    pose_summary: dict = Field(default_factory=dict)
    parsing_summary: dict = Field(default_factory=dict)
