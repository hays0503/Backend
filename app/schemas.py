import math
import re
from functools import wraps
from typing import Optional
from flask import request, jsonify, current_app
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError, field_validator, model_validator

MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class ProfileUpdate(BaseModel):
    current_password: str = Field(min_length=1)
    username: Optional[str] = None
    password: Optional[str] = None


class ReadingItem(BaseModel):
    address: str = Field(min_length=1, max_length=64)
    temperature: float
    recorded_at: int

    @field_validator("temperature")
    @classmethod
    def temperature_is_finite(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("temperature must be a finite number")
        return v

    @field_validator("recorded_at")
    @classmethod
    def recorded_at_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("recorded_at must be a positive timestamp")
        return v


class SensorDataBatch(BaseModel):
    controller_mac: str = Field(min_length=1, max_length=32)
    readings: list[ReadingItem]
    keep_count: int = Field(default=1000, ge=1, le=10000)

    @field_validator("controller_mac")
    @classmethod
    def mac_format(cls, v: str) -> str:
        if not MAC_RE.match(v):
            raise ValueError(
                "controller_mac must be a valid MAC address (e.g. AA:BB:CC:DD:EE:FF)"
            )
        return v

    @model_validator(mode="after")
    def validate_batch_and_timestamps(self):
        cfg = current_app.config
        max_batch = cfg.get("MAX_BATCH_SIZE", 100)
        if len(self.readings) > max_batch:
            raise ValueError(f"readings list exceeds maximum of {max_batch} items")
        if len(self.readings) == 0:
            raise ValueError("readings must not be empty")

        temp_min = cfg.get("TEMP_MIN", -50.0)
        temp_max = cfg.get("TEMP_MAX", 150.0)
        window_ms = cfg.get("TIMESTAMP_WINDOW_HOURS", 24) * 3600 * 1000
        now_ms = int(__import__("time").time() * 1000)

        for i, r in enumerate(self.readings):
            if not (temp_min <= r.temperature <= temp_max):
                raise ValueError(
                    f"readings[{i}].temperature={r.temperature} out of bounds [{temp_min}, {temp_max}]"
                )
            age = now_ms - r.recorded_at
            if age > window_ms:
                raise ValueError(
                    f"readings[{i}].recorded_at is older than {window_ms // 3600000}h"
                )
            if r.recorded_at > now_ms + 60000:
                raise ValueError("readings[{}].recorded_at is in the future".format(i))

        self.keep_count = min(self.keep_count, cfg.get("MAX_KEEP_COUNT", 10000))
        return self


class RenameSensorRequest(BaseModel):
    sensor_id: int
    location: str = Field(min_length=1)


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=1)


class AssignControllersRequest(BaseModel):
    controllers: list[str]


def use_schema(schema_class):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            raw = request.get_json(silent=True)
            if raw is None:
                from .errors import ValidationError
                raise ValidationError("Request body must be valid JSON")
            try:
                obj = schema_class(**raw)
            except PydanticValidationError as e:
                from .errors import ValidationError
                details = []
                for err in e.errors():
                    field = ".".join(str(x) for x in err["loc"])
                    details.append({"field": field, "message": err["msg"]})
                raise ValidationError(details=details)
            return f(obj, *args, **kwargs)
        return wrapper
    return decorator
