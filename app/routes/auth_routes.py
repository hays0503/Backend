import secrets

from flask import Blueprint, current_app, g, request

from .. import limiter
from ..audit import log_action
from ..auth import (
    clear_auth_cookies,
    decode_token,
    require_auth,
    revoke_session,
    set_auth_cookies,
    set_csrf_cookie,
)
from ..config import Config
from ..db import get_db
from ..errors import ValidationError
from ..responses import ok
from ..schemas import LoginRequest, ProfileUpdate, use_schema
from ..services import auth_service

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
@use_schema(LoginRequest)
def login(data):
    result = auth_service.login(data.username, data.password)
    log_action(
        result["user"]["id"],
        result["user"]["username"],
        "login",
    )
    resp, status_code = ok(result)
    set_auth_cookies(resp, result["access_token"], result["refresh_token"])
    set_csrf_cookie(resp)
    return resp, status_code


@auth_bp.route("/refresh", methods=["POST"])
@limiter.limit("5 per minute")
def refresh():
    raw = request.get_json(silent=True) or {}
    refresh_token = raw.get("refresh_token") or request.cookies.get(
        Config.REFRESH_COOKIE_NAME
    )
    if not refresh_token:
        raise ValidationError("Refresh token is required")
    result = auth_service.refresh(refresh_token)
    resp, status_code = ok(result)
    set_auth_cookies(resp, result["access_token"], result["refresh_token"])
    set_csrf_cookie(resp)
    return resp, status_code


@auth_bp.route("/logout", methods=["POST"])
@limiter.limit("20 per minute")
def logout():
    refresh_token = request.cookies.get(Config.REFRESH_COOKIE_NAME)
    if refresh_token:
        payload = decode_token(refresh_token, "refresh")
        if payload:
            revoke_session(payload["jti"])
            username = get_db().execute(
                "SELECT username FROM users WHERE id = ?", (payload["user_id"],)
            ).fetchone()
            log_action(
                payload["user_id"],
                username[0] if username else str(payload["user_id"]),
                "logout",
            )
    resp = current_app.response_class("", status=204)
    clear_auth_cookies(resp)
    return resp


@auth_bp.route("/csrf-token", methods=["GET"])
@limiter.limit("60 per minute")
def csrf_token():
    token = request.cookies.get(Config.CSRF_COOKIE_NAME) or secrets.token_urlsafe(32)
    resp, status_code = ok({"csrf_token": token})
    set_csrf_cookie(resp, token)
    return resp, status_code


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
