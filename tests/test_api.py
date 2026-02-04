import uuid
from datetime import date as date_type  # noqa: F401
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


# ----------------------------
# Helpers (robust for shared DB)
# ----------------------------


def _unique_email() -> str:
    return f"test_{uuid.uuid4().hex[:10]}@example.com"


def _unique_name(prefix: str) -> str:
    return f"{prefix} {uuid.uuid4().hex[:8]}"


def _create_patient_id(max_tries: int = 8) -> int:
    """
    Tries to create a patient until it succeeds (201).
    If DB uniqueness or shared state causes conflicts, retries with a new email.
    """
    for _ in range(max_tries):
        payload = {
            "first_name": "Test",
            "last_name": _unique_name("Patient"),
            "email": _unique_email(),
            "phone": "9999999999",
        }
        r = client.post("/patients", json=payload)
        if r.status_code == 201:
            data = r.json()
            if "id" in data:
                return int(data["id"])
        # If conflict/validation, retry with new unique email/name
        if r.status_code in (400, 409, 422):
            continue

        pytest.fail(
            f"Unexpected status for create patient: {r.status_code}, body={r.text}"
        )

    pytest.fail("Could not create a patient after retries (shared DB may be unstable).")


def _create_doctor_id(max_tries: int = 8) -> int:
    """
    Tries to create a doctor until it succeeds (201).
    Uses unique full_name so it shouldn't collide.
    """
    for _ in range(max_tries):
        payload = {
            "full_name": _unique_name("Dr"),
            "specialization": "Cardiology",
            "is_active": True,
        }
        r = client.post("/doctors", json=payload)
        if r.status_code == 201:
            data = r.json()
            if "id" in data:
                return int(data["id"])

        if r.status_code in (400, 409, 422):
            continue

        pytest.fail(
            f"Unexpected status for create doctor: {r.status_code}, body={r.text}"
        )

    pytest.fail("Could not create a doctor after retries (shared DB may be unstable).")


def _future_time(minutes_from_now: int = 60) -> str:
    dt = datetime.now(timezone.utc) + timedelta(minutes=minutes_from_now)
    dt = dt.replace(second=0, microsecond=0)
    return dt.isoformat()


def _tomorrow_date() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()


# ----------------------------
# Patient tests
# ----------------------------


def test_create_patient_success():
    pid = _create_patient_id()
    assert isinstance(pid, int) and pid > 0


def test_get_patient_by_id_200():
    pid = _create_patient_id()
    r = client.get(f"/patients/{pid}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == pid
    assert "email" in data


def test_get_patient_by_id_404():
    r = client.get("/patients/999999999")
    assert r.status_code == 404


def test_patient_email_validation_rejects_bad_email():
    payload = {
        "first_name": "Bad",
        "last_name": "Email",
        "email": "not-an-email",
        "phone": "9999999999",
    }
    r = client.post("/patients", json=payload)
    # Depending on schema, invalid email is usually 422
    assert r.status_code in (400, 422)


# ----------------------------
# Doctor tests
# ----------------------------


def test_create_doctor_success():
    did = _create_doctor_id()
    assert isinstance(did, int) and did > 0


def test_get_doctor_by_id_200():
    did = _create_doctor_id()
    r = client.get(f"/doctors/{did}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == did
    assert "specialization" in data


def test_get_doctor_by_id_404():
    r = client.get("/doctors/999999999")
    assert r.status_code == 404


# ----------------------------
# Appointment validation tests
# ----------------------------


def test_reject_naive_datetime_422():
    pid = _create_patient_id()
    did = _create_doctor_id()
    payload = {
        "patient_id": pid,
        "doctor_id": did,
        "start_time_utc": "2026-02-02T10:00:00",  # ❌ no timezone
        "duration_minutes": 30,
    }
    r = client.post("/appointments", json=payload)
    assert r.status_code == 422


def test_reject_duration_too_short_400():
    pid = _create_patient_id()
    did = _create_doctor_id()
    payload = {
        "patient_id": pid,
        "doctor_id": did,
        "start_time_utc": _future_time(120),
        "duration_minutes": 10,  # ❌ below 15
    }
    r = client.post("/appointments", json=payload)
    assert r.status_code in (400, 422)


def test_reject_duration_too_long_400():
    pid = _create_patient_id()
    did = _create_doctor_id()
    payload = {
        "patient_id": pid,
        "doctor_id": did,
        "start_time_utc": _future_time(120),
        "duration_minutes": 181,  # ❌ above 180
    }
    r = client.post("/appointments", json=payload)
    assert r.status_code in (400, 422)


def test_reject_past_appointment_400():
    pid = _create_patient_id()
    did = _create_doctor_id()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    payload = {
        "patient_id": pid,
        "doctor_id": did,
        "start_time_utc": past,
        "duration_minutes": 30,
    }
    r = client.post("/appointments", json=payload)
    assert r.status_code in (400, 422)


def test_reject_missing_patient_404():
    did = _create_doctor_id()
    payload = {
        "patient_id": 999999999,
        "doctor_id": did,
        "start_time_utc": _future_time(120),
        "duration_minutes": 30,
    }
    r = client.post("/appointments", json=payload)
    assert r.status_code == 404


def test_reject_missing_doctor_404():
    pid = _create_patient_id()
    payload = {
        "patient_id": pid,
        "doctor_id": 999999999,
        "start_time_utc": _future_time(120),
        "duration_minutes": 30,
    }
    r = client.post("/appointments", json=payload)
    assert r.status_code == 404


# ----------------------------
# Appointment core rule tests
# ----------------------------


def test_create_appointment_success_201():
    pid = _create_patient_id()
    did = _create_doctor_id()
    payload = {
        "patient_id": pid,
        "doctor_id": did,
        "start_time_utc": _future_time(180),
        "duration_minutes": 30,
    }
    r = client.post("/appointments", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["doctor_id"] == did
    assert data["patient_id"] == pid


def test_appointment_overlap_returns_409():
    """
    Make a fresh doctor to reduce chance of pre-existing appts.
    Then create appt A and appt B that overlaps => 409 expected.
    """
    pid = _create_patient_id()
    did = _create_doctor_id()

    start = _future_time(240)  # 4 hours from now
    payload = {
        "patient_id": pid,
        "doctor_id": did,
        "start_time_utc": start,
        "duration_minutes": 60,
    }

    r1 = client.post("/appointments", json=payload)
    assert r1.status_code == 201, f"Expected 201, got {r1.status_code}, body={r1.text}"

    # overlap within the first appointment window
    payload2 = {
        "patient_id": pid,
        "doctor_id": did,
        "start_time_utc": start,  # exact same start => overlap
        "duration_minutes": 30,
    }
    r2 = client.post("/appointments", json=payload2)
    assert r2.status_code == 409, f"Expected 409, got {r2.status_code}, body={r2.text}"


# ----------------------------
# PDF contract: list appointments by date
# ----------------------------


def test_get_appointments_by_date_returns_list():
    target_date = _tomorrow_date()
    r = client.get(f"/appointments?date={target_date}")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_appointments_by_date_with_doctor_filter_returns_list():
    did = _create_doctor_id()
    target_date = _tomorrow_date()
    r = client.get(f"/appointments?date={target_date}&doctor_id={did}")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_appointments_by_date_bad_date_422_or_400():
    r = client.get("/appointments?date=not-a-date")
    assert r.status_code in (400, 422)


def test_get_appointments_by_date_bad_doctor_id_400_or_422():
    target_date = _tomorrow_date()
    r = client.get(f"/appointments?date={target_date}&doctor_id=-1")
    assert r.status_code in (400, 422)
