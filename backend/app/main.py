from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .config import VERSION, ALLOWED_ORIGINS
from .security import get_current_user
from .models import entities  # noqa: F401
from .migrate import migrate_schema
from .routers import auth, fitness, body, prescriptions, sessions, reports, devices, demo, demo_videos, pose_infer, onboarding, kb


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate_schema()
    yield


app = FastAPI(title="Active Health Intelligent Service", version=VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def validate_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in ALLOWED_ORIGINS:
        return JSONResponse(status_code=403, content={"detail": "请求来源未获允许"})
    response = await call_next(request)
    # Personal API responses and auth tokens must not enter shared browser/proxy caches.
    response.headers["Cache-Control"] = "no-store"
    return response

app.include_router(auth.router)
app.include_router(auth.users_router)
app.include_router(fitness.router)
app.include_router(body.router)
app.include_router(prescriptions.router)
app.include_router(sessions.router)
app.include_router(reports.router)
app.include_router(devices.router)
app.include_router(demo.router)
app.include_router(demo_videos.router)
app.include_router(pose_infer.router, dependencies=[Depends(get_current_user)])
app.include_router(onboarding.router)
app.include_router(kb.router)


@app.get("/health")
def health():
    return {"status": "ok", "version": VERSION, "message": "主动健康系统框架后端就绪"}
