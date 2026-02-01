from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_serializer


def _as_utc_tzaware(dt: datetime) -> datetime:
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class DoctorCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=200)
    specialization: str = Field(..., min_length=1, max_length=100)
    is_active: bool = True


class DoctorRead(BaseModel):
    id: int
    full_name: str
    specialization: str
    is_active: bool
    created_at: datetime

    model_config = {"from attributes": True}

    @field_serializer("created_at", when_used="json")
    def _ser_dt(self, v: datetime) -> datetime:
        return _as_utc_tzaware(v)
