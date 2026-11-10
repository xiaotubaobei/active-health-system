from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..security import get_current_user, require_owner
from ..models.entities import BodyMetrics, User
from ..schemas.dto import BodyParseIn
from ..services import ai_client
from ..services.media_access import media_path

router = APIRouter(prefix="/body", tags=["body"])


@router.post("/parse")
async def parse_body(body: BodyParseIn, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = require_owner(body.user_id, actor)
    media_path(body.image_path, actor.id)
    parsing = await ai_client.parsing_analyze(
        {"image_path": body.image_path, "clicks": body.clicks, "text_prompt": "person body parts"}
    )
    h_m = max(user.height_cm, 1) / 100.0
    bmi = round(user.weight_kg / (h_m * h_m), 2)
    whr = 0.0
    if body.waist_cm and body.hip_cm and body.hip_cm > 0:
        whr = round(body.waist_cm / body.hip_cm, 3)
    row = BodyMetrics(
        user_id=user.id,
        bmi=bmi,
        whr=whr,
        body_fat=body.body_fat or 0.0,
        parsing_result=parsing,
        image_path=body.image_path,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    history = (
        db.query(BodyMetrics)
        .filter(BodyMetrics.user_id == user.id)
        .order_by(BodyMetrics.created_at.desc())
        .limit(5)
        .all()
    )
    return {"current": row, "history": history}
