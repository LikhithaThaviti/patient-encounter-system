from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException

from src.models.doctor import Doctor
from src.schemas.doctor import DoctorCreate

def create_doctor(db: Session, doctor_create: DoctorCreate) -> Doctor:
    obj = Doctor(
        full_name=doctor_create.full_name,
        is_active=doctor_create.is_active,
        specialization=doctor_create.specialization
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
def get_doctor(db: Session, doctor_id: int) -> Doctor:
    obj = db.get(Doctor, doctor_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Doctor not found.")
    return obj

def list_doctors(db: Session) -> list[Doctor]:
    return list(db.scalars(select(Doctor).order_by(Doctor.id)))