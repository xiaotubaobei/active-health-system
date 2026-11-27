"""Authenticated access to the current user's uploaded training media."""
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from ..models.entities import User
from ..security import get_current_user
from ..services.media_access import media_path

router = APIRouter(prefix="/uploads", tags=["media"])


@router.get("/{relative_path:path}")
def read_own_upload(relative_path: str, actor: User = Depends(get_current_user)):
    path = media_path(f"uploads/{relative_path}", actor.id, must_exist=True)
    response = FileResponse(path, filename=path.name, content_disposition_type="inline")
    response.headers["Cache-Control"] = "private, no-store"
    return response
