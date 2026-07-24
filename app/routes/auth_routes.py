from flask import Blueprint, g
from ..auth import require_auth
from ..audit import log_action
from ..responses import ok
from ..schemas import use_schema, LoginRequest, RefreshRequest, ProfileUpdate
from ..services import auth_service

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
@use_schema(LoginRequest)
def login(data):
    result = auth_service.login(data.username, data.password)
    log_action(
        result["user"]["id"],
        result["user"]["username"],
        "login",
    )
    return ok(result)


@auth_bp.route("/refresh", methods=["POST"])
@use_schema(RefreshRequest)
def refresh(data):
    result = auth_service.refresh(data.refresh_token)
    return ok(result)


@auth_bp.route("/me")
@require_auth
def auth_me():
    result = auth_service.get_current_user(g.user_id)
    return ok(result)


@auth_bp.route("/profile", methods=["PUT"])
@require_auth
@use_schema(ProfileUpdate)
def auth_profile(data):
    result = auth_service.update_profile(
        g.user_id,
        data.current_password,
        data.username,
        data.password,
    )
    log_action(g.user_id, result["username"], "profile_updated")
    return ok(result)
