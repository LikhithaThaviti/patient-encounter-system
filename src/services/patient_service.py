from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from src.models.patient import Patient
from src.schemas.patient import PatientCreate

def create_patient(db: Session, patient_create: PatientCreate) -> Patient:
    existing = db.execute(
        select(Patient).where(Patient.email == patient_create.email.strip().lower())).scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="Patient with this email already exists.")
    obj = Patient(
        first_name=patient_create.first_name,
        last_name=patient_create.last_name,
        email=patient_create.email.strip().lower(),
        phone=patient_create.phone
    )
    db.add(obj)
    try:
       db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code = 400,
            detail = "Duplicate email",
        )
    db.refresh(obj)
    return obj


def get_patient(db: Session, patient_id: int) -> Patient:
    obj = db.get(Patient, patient_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    return obj

def list_patients(db: Session) -> list[Patient]:
    return list(db.scalars(select(Patient).order_by(Patient.id)))

