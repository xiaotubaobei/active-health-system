from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..security import get_current_user, owned_user, require_owner
from ..models.entities import DeviceReading, User
from ..schemas.dto import DeviceReadingIn

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/readings")
def add_reading(body: DeviceReadingIn, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_owner(body.user_id, actor)
    row = DeviceReading(user_id=body.user_id, device_type=body.device_type, payload=body.payload)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/readings")
def list_readings(user_id: int, user: User = Depends(owned_user), db: Session = Depends(get_db)):
    return (
        db.query(DeviceReading)
        .filter(DeviceReading.user_id == user_id)
        .order_by(DeviceReading.created_at.desc())
        .limit(50)
        .all()
    )
