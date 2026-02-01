from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from src import models  # noqa: F401
from src.database import Base, engine, get_db
from src.schemas.appointment import AppointmentCreate, AppointmentRead
from src.schemas.doctor import DoctorCreate, DoctorRead
from src.schemas.patient import PatientCreate, PatientRead
from src.services.appointment_service import (
    create_appointment,
    get_appointment,
    list_appointments,
)
from src.services.doctor_service import create_doctor, get_doctor, list_doctors
from src.services.patient_service import create_patient, get_patient, list_patients

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Patient encounter system", lifespan=lifespan)


@app.get("/")
def root():
    return {"messages": "API is running", "health": "/health", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/patients", response_model=PatientRead, status_code=201)
def api_create_patient(payload: PatientCreate, db: Session = Depends(get_db)):
    return create_patient(db, payload)


@app.get("/patients", response_model=list[PatientRead])
def api_list_patients(db: Session = Depends(get_db)):
    return list_patients(db)


@app.get("/patients/{patient_id}", response_model=PatientRead)
def api_get_patient(patient_id: int, db: Session = Depends(get_db)):
    return get_patient(db, patient_id)


@app.post("/doctors", response_model=DoctorRead, status_code=201)
def api_create_doctor(payload: DoctorCreate, db: Session = Depends(get_db)):
    return create_doctor(db, payload)


@app.get("/doctors", response_model=list[DoctorRead])
def api_list_doctors(db: Session = Depends(get_db)):
    return list_doctors(db)


@app.get("/doctors/{doctor_id}", response_model=DoctorRead)
def api_get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    return get_doctor(db, doctor_id)


@app.post("/appointments", response_model=AppointmentRead, status_code=201)
def api_create_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)):
    return create_appointment(db, payload)


@app.get("/appointments", response_model=list[AppointmentRead])
def api_list_appointments(db: Session = Depends(get_db)):
    return list_appointments(db)


@app.get("/appointments/{appointment_id}", response_model=AppointmentRead)
def api_get_appointment(appointment_id: int, db: Session = Depends(get_db)):
    return get_appointment(db, appointment_id)
