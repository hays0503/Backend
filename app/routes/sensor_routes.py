from flask import Blueprint, request, g
from ..auth import require_auth
from ..audit import log_action
from ..responses import ok
from ..schemas import use_schema, SensorDataBatch, RenameSensorRequest
from ..device_auth import require_device_auth
from ..services import sensor_service
from ..services.user_service import _get_username
from .. import limiter

sensor_bp = Blueprint("sensor", __name__, url_prefix="/api/sensor")
device_bp = Blueprint("device", __name__, url_prefix="/api/device")


@sensor_bp.route("/data", methods=["POST"])
@require_device_auth
@limiter.limit("50 per second")
@use_schema(SensorDataBatch)
def post_sensor_data(data):
    result = sensor_service.ingest_readings(
        data.controller_mac, data.readings, data.keep_count
    )
    return ok(result, 201)


@sensor_bp.route("/data", methods=["GET"])
@require_auth
def get_sensor_data():
    sensor_id = request.args.get("sensor_id", type=int)
    if not sensor_id:
        from ..errors import ValidationError
        raise ValidationError("sensor_id is required")
    result = sensor_service.get_recent_readings(sensor_id, g.user_id)
    return ok(result)


@sensor_bp.route("/rename", methods=["PUT"])
@require_auth
@use_schema(RenameSensorRequest)
def rename_sensor(data):
    sensor_service.rename_sensor(data.sensor_id, data.location, g.user_id)
    username = _get_username(g.user_id)
    log_action(
        g.user_id,
        username,
        "sensor_renamed",
        "sensor",
        str(data.sensor_id),
        {"location": data.location},
    )
    return ok()


@device_bp.route("/info")
@require_auth
def device_info():
    result = sensor_service.get_device_info(g.user_id)
    return ok(result)
