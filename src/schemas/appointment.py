from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_serializer, field_validator


def _as_utc_tzaware(dt: datetime) -> datetime:
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
    start_time_utc: datetime
    duration_minutes: int = Field(ge=15, le=180)

    @field_validator("start_time_utc")
    @classmethod
    def require_tz_and_normalize_to_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("start_time_utc must be timezone-aware.")
        return v.astimezone(timezone.utc)


class AppointmentRead(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    start_time_utc: datetime
    duration_minutes: int
    created_at: datetime

    model_config = {"from attributes": True}

    @field_serializer("start_time_utc", "created_at", when_used="json")
    def _ser_dt(self, v: datetime) -> datetime:
        return _as_utc_tzaware(v)
