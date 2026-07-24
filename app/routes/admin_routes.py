from flask import Blueprint, g
from ..auth import require_auth, require_admin
from ..audit import log_action
from ..responses import ok
from ..schemas import (
    use_schema,
    CreateUserRequest,
    ResetPasswordRequest,
    AssignControllersRequest,
)
from ..services import user_service, audit_service
from ..services.user_service import _get_username

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def parse_pagination_args():
    from flask import request
    limit = request.args.get("limit", DEFAULT_PAGE_SIZE, type=int)
    offset = request.args.get("offset", 0, type=int)
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, offset)
    return limit, offset


@admin_bp.route("/users")
@require_auth
@require_admin
def admin_list_users():
    limit, offset = parse_pagination_args()
    result = user_service.list_users(limit, offset)
    return ok(result)


@admin_bp.route("/users", methods=["POST"])
@require_auth
@require_admin
@use_schema(CreateUserRequest)
def admin_create_user(data):
    result = user_service.create_user(data.username, data.password)
    username = _get_username(g.user_id)
    log_action(
        g.user_id,
        username,
        "user_created",
        "user",
        str(result["id"]),
        {"username": data.username},
    )
    return ok(result, 201)


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@require_auth
@require_admin
def admin_delete_user(user_id):
    user_service.delete_user(user_id)
    username = _get_username(g.user_id)
    log_action(g.user_id, username, "user_deleted", "user", str(user_id))
    return ok()


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["PUT"])
@require_auth
@require_admin
@use_schema(ResetPasswordRequest)
def admin_reset_password(data, user_id):
    user_service.reset_password(user_id, data.new_password)
    username = _get_username(g.user_id)
    log_action(g.user_id, username, "password_reset", "user", str(user_id))
    return ok()


@admin_bp.route("/users/<int:user_id>/controllers", methods=["PUT"])
@require_auth
@require_admin
@use_schema(AssignControllersRequest)
def admin_assign_controllers(data, user_id):
    user_service.assign_controllers(user_id, data.controllers)
    username = _get_username(g.user_id)
    log_action(
        g.user_id,
        username,
        "controllers_assigned",
        "user",
        str(user_id),
        {"controllers": data.controllers},
    )
    return ok()


@admin_bp.route("/controllers")
@require_auth
@require_admin
def admin_list_controllers():
    limit, offset = parse_pagination_args()
    result = user_service.list_controllers(limit, offset)
    return ok(result)


@admin_bp.route("/audit")
@require_auth
@require_admin
def admin_audit():
    limit, offset = parse_pagination_args()
    result = audit_service.get_audit_log(limit, offset)
    return ok(result)
