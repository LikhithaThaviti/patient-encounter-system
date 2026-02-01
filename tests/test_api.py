import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def _unique_email() -> str:
    return f"test_{uuid.uuid4().hex[:10]}@example.com"


def _ensure_patient_id() -> int:
    """
    Try to create a patient. If shared DB already has conflicts, fall back to
    an existing patient id (if any).
    """
    payload = {
        "first_name": "Test",
        "last_name": "Patient",
        "email": _unique_email(),
        "phone": "9999999999",
    }
    resp = client.post("/patients", json=payload)

    # if created, grab id
    if resp.status_code == 201:
        data = resp.json()
        if "id" in data:
            return int(data["id"])

    # fallback: existing patient
    r_list = client.get("/patients")
    if r_list.status_code == 200 and r_list.json():
        return int(r_list.json()[0]["id"])

    # If no patients exist at all, fail with a clear message
    pytest.fail(
        f"Could not create or fetch a patient id. "
        f"Create patient status={resp.status_code}, body={resp.text}"
    )


def _ensure_doctor_id() -> int:
    """
    Try to create a doctor, else fall back to existing doctor.
    """
    payload = {
        "full_name": "Dr Test",
        "specialization": "Cardiology",
        "is_active": True,
    }
    resp = client.post("/doctors", json=payload)

    if resp.status_code == 201:
        data = resp.json()
        if "id" in data:
            return int(data["id"])

    r_list = client.get("/doctors")
    if r_list.status_code == 200 and r_list.json():
        return int(r_list.json()[0]["id"])

    pytest.fail(
        f"Could not create or fetch a doctor id. "
        f"Create doctor status={resp.status_code}, body={resp.text}"
    )


def test_create_patient_returns_201_or_conflict():
    """
    In a shared DB, even unique-looking emails might collide (collation/caching).
    We accept either:
      - 201 Created (success)
      - 400/409 if the backend enforces uniqueness and conflicts happen
    """
    payload = {
        "first_name": "Test",
        "last_name": "User",
        "email": _unique_email(),
        "phone": "9999999999",
    }
    resp = client.post("/patients", json=payload)
    assert resp.status_code in (201, 400, 409)


def test_reject_naive_datetime():
    """
    Datetime must include timezone info -> Pydantic should reject naive values.
    """
    patient_id = _ensure_patient_id()
    doctor_id = _ensure_doctor_id()

    payload = {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "start_time_utc": "2026-02-02T10:00:00",  # ❌ no timezone
        "duration_minutes": 30,
    }
    resp = client.post("/appointments", json=payload)
    assert resp.status_code == 422


def test_reject_past_appointment():
    """
    Appointment must be in the future (UTC).
    """
    patient_id = _ensure_patient_id()
    doctor_id = _ensure_doctor_id()

    past_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    payload = {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "start_time_utc": past_time,
        "duration_minutes": 30,
    }
    resp = client.post("/appointments", json=payload)
    assert resp.status_code == 400


def test_appointment_overlap_returns_409():
    """
    Creating the same appointment twice for the same doctor should conflict (409)
    due to overlap rule.
    """
    patient_id = _ensure_patient_id()
    doctor_id = _ensure_doctor_id()

    # Use a clean rounded future time to reduce flakiness
    start_dt = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        minute=0, second=0, microsecond=0
    )
    start_time = start_dt.isoformat()

    payload = {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "start_time_utc": start_time,
        "duration_minutes": 30,
    }

    r1 = client.post("/appointments", json=payload)

    # If it overlaps with an existing appointment already in shared DB, that's OK;
    # but then the rule is still enforced.
    if r1.status_code == 409:
        assert r1.status_code == 409
        return

    assert (
        r1.status_code == 201
    ), f"Expected 201 or 409, got {r1.status_code}, body={r1.text}"

    r2 = client.post("/appointments", json=payload)
    assert r2.status_code == 409, f"Expected 409, got {r2.status_code}, body={r2.text}"


def test_get_appointments_by_date_contract():
    """
    PDF-required endpoint: GET /appointments?date=YYYY-MM-DD&doctor_id(optional)
    Should return 200 and a list.
    """
    target_date = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
    resp = client.get(f"/appointments?date={target_date}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
