from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.entities import DeviceReading, User
from ..schemas.dto import DeviceReadingIn

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/readings")
def add_reading(body: DeviceReadingIn, db: Session = Depends(get_db)):
    if not db.get(User, body.user_id):
        raise HTTPException(404, "用户不存在")
    row = DeviceReading(user_id=body.user_id, device_type=body.device_type, payload=body.payload)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/readings")
def list_readings(user_id: int, db: Session = Depends(get_db)):
    return (
        db.query(DeviceReading)
        .filter(DeviceReading.user_id == user_id)
        .order_by(DeviceReading.created_at.desc())
        .limit(50)
        .all()
    )
