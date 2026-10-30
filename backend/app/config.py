from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
UPLOAD_DIR = ROOT / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'active_health.db'}")

AI_ENDPOINTS = {
    "pose": os.getenv("AI_POSE_URL", "http://127.0.0.1:8101"),
    "pose_kb": os.getenv("AI_POSE_KB_URL", "http://127.0.0.1:8102"),
    "video_gen": os.getenv("AI_VIDEO_GEN_URL", "http://127.0.0.1:8103"),
    "parsing": os.getenv("AI_PARSING_URL", "http://127.0.0.1:8104"),
    "visual_encoder": os.getenv("AI_VISUAL_ENCODER_URL", "http://127.0.0.1:8105"),
    "behavior": os.getenv("AI_BEHAVIOR_URL", "http://127.0.0.1:8106"),
    "video_cot": os.getenv("AI_VIDEO_COT_URL", "http://127.0.0.1:8107"),
}

SECRET_KEY = os.getenv("SECRET_KEY", "active-health-dev-secret")
VERSION = "0.2.0-demo"