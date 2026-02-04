from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.appointment import Appointment
from src.models.doctor import Doctor
from src.models.patient import Patient
from src.schemas.appointment import AppointmentCreate


def _as_utc(dt: datetime) -> datetime:
    """
    Ensure datetime is timezone-aware UTC.
    - If DB returns naive datetime (common with MySQL DATETIME), treat it as UTC.
    - If aware, convert to UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _require_timezone_aware(dt: datetime) -> None:
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise HTTPException(
            status_code=400,
            detail="start_time_utc must be timezone-aware (include timezone info).",
        )


def _validate_duration(minutes: int) -> None:
    if minutes < 15 or minutes > 180:
        raise HTTPException(
            status_code=400,
            detail="duration_minutes must be between 15 and 180 minutes.",
        )


def _ensure_patient_exists(db: Session, patient_id: int) -> None:
    exists = db.scalar(select(Patient.id).where(Patient.id == patient_id))
    if not exists:
        raise HTTPException(status_code=404, detail="Patient not found.")


def _ensure_doctor_exists(db: Session, doctor_id: int) -> None:
    exists = db.scalar(select(Doctor.id).where(Doctor.id == doctor_id))
    if not exists:
        raise HTTPException(status_code=404, detail="Doctor not found.")


# ----------------------------
# Core Service Functions
# ----------------------------


def create_appointment(db: Session, data: AppointmentCreate) -> Appointment:
    """
    Create an appointment enforcing:
    - timezone-aware datetime
    - future-only
    - duration 15–180
    - no overlap for same doctor (409)
    """
    # Validate IDs are positive (PDF mentions this; schema likely also enforces)
    if data.patient_id <= 0 or data.doctor_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="patient_id and doctor_id must be positive integers.",
        )

    _require_timezone_aware(data.start_time_utc)
    _validate_duration(data.duration_minutes)

    _ensure_patient_exists(db, data.patient_id)
    _ensure_doctor_exists(db, data.doctor_id)

    new_start = _as_utc(data.start_time_utc)
    now_utc = datetime.now(timezone.utc)

    if new_start <= now_utc:
        raise HTTPException(
            status_code=400, detail="Appointment must be scheduled in the future."
        )

    new_end = new_start + timedelta(minutes=data.duration_minutes)

    # Fetch candidate existing appointments for same doctor.
    # We only need ones that start before our new_end to overlap potentially.
    candidates = db.scalars(
        select(Appointment).where(
            Appointment.doctor_id == data.doctor_id,
            Appointment.start_time_utc < new_end,  # potential overlap
        )
    ).all()

    # Overlap rule: new_start < existing_end AND new_end > existing_start
    for appt in candidates:
        ex_start = _as_utc(appt.start_time_utc)
        ex_end = ex_start + timedelta(minutes=appt.duration_minutes)

        if new_start < ex_end and new_end > ex_start:
            raise HTTPException(
                status_code=409, detail="Doctor has a conflicting appointment."
            )

    obj = Appointment(
        patient_id=data.patient_id,
        doctor_id=data.doctor_id,
        start_time_utc=new_start,  # stored in UTC
        duration_minutes=data.duration_minutes,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_appointment(db: Session, appointment_id: int) -> Appointment:
    appt = db.scalar(select(Appointment).where(Appointment.id == appointment_id))
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    return appt


def list_appointments(db: Session) -> List[Appointment]:
    return db.scalars(
        select(Appointment).order_by(Appointment.start_time_utc.asc())
    ).all()


def list_appointments_by_date(
    db: Session, target_date: date, doctor_id: Optional[int] = None
) -> List[Appointment]:
    """
    PDF-required contract:
      GET /appointments?date=YYYY-MM-DD&doctor_id(optional)

    We interpret "date" in UTC day boundaries.
    """
    start_dt = datetime(
        target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc
    )
    end_dt = start_dt + timedelta(days=1)

    stmt = select(Appointment).where(
        Appointment.start_time_utc >= start_dt,
        Appointment.start_time_utc < end_dt,
    )

    if doctor_id is not None:
        if doctor_id <= 0:
            raise HTTPException(
                status_code=400, detail="doctor_id must be a positive integer."
            )
        stmt = stmt.where(Appointment.doctor_id == doctor_id)

    stmt = stmt.order_by(Appointment.start_time_utc.asc())
    return db.scalars(stmt).all()
