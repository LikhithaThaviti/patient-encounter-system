from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException

from src.models.appointment import Appointment
from src.schemas.appointment import AppointmentCreate
from src.models.patient import Patient
from src.models.doctor import Doctor

def create_appointment(db: Session, appointment_create: AppointmentCreate) -> Appointment:
    patient = db.get(Patient, appointment_create.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    
    doctor = db.get(Doctor, appointment_create.doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found.")
    
    if not doctor.is_active:
        raise HTTPException(status_code=400, detail="Doctor is not active.")
    
    start_utc= appointment_create.start_time_utc
    now_utc = datetime.now(timezone.utc)
    if start_utc <= now_utc:
        raise HTTPException(status_code=400, detail="Appointment time must be in the future.")
    
    end_utc = start_utc + timedelta(minutes=appointment_create.duration_minutes)
    existing = list(
        db.scalars(
            select(Appointment).where(Appointment.doctor_id == appointment_create.doctor_id)
        )
    )

    for appt in existing:
        appt_start = appt.start_time_utc
        if appt_start.tzinfo is None or appt_start.utcoffset() is None:
            appt_start = appt_start.replace(tzinfo=timezone.utc)
        appt_end = appt_start + timedelta(minutes=appt.duration_minutes)
        if (start_utc < end_utc) and (appt_end > start_utc):
            raise HTTPException(status_code=400, detail="Doctor has a conflicting appointment.")
        
    obj = Appointment(
        patient_id=appointment_create.patient_id,
        doctor_id=appointment_create.doctor_id,
        start_time_utc=start_utc.replace(tzinfo=None),
        duration_minutes=appointment_create.duration_minutes,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def get_appointment(db: Session, appointment_id: int) -> Appointment:
    obj = db.get(Appointment, appointment_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    return obj

def list_appointments(db: Session) -> list[Appointment]:
    return list(db.scalars(select(Appointment).order_by(Appointment.start_time_utc)))