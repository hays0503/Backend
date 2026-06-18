from functools import wraps
from typing import Optional
from flask import request, jsonify
from pydantic import BaseModel, Field, ValidationError


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
    address: str = Field(min_length=1)
    temperature: float
    recorded_at: int


class SensorDataBatch(BaseModel):
    controller_mac: str = Field(min_length=1)
    readings: list[ReadingItem]
    keep_count: int = Field(default=1000, ge=1)


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
    """Validates request JSON against a Pydantic schema and passes
    the validated object as the first positional argument."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            raw = request.get_json(silent=True)
            if raw is None:
                return jsonify({"error": "Request body must be valid JSON"}), 400
            try:
                obj = schema_class(**raw)
            except ValidationError as e:
                first = e.errors()[0]
                field = ".".join(str(x) for x in first["loc"])
                return jsonify({"error": f"{field}: {first['msg']}"}), 400
            return f(obj, *args, **kwargs)
        return wrapper
    return decorator
