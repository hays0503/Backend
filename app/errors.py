import logging
import traceback
from flask import jsonify, request, g, current_app


class APIError(Exception):
    """Base application error with structured response."""

    def __init__(self, code, message, status_code=400, details=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)

    def to_dict(self):
        body = {"code": self.code, "message": self.message}
        if self.details:
            body["details"] = self.details
        return {"error": body}


class NotFoundError(APIError):
    def __init__(self, message="Resource not found", details=None):
        super().__init__("NOT_FOUND", message, 404, details)


class ValidationError(APIError):
    def __init__(self, message="Validation failed", details=None):
        super().__init__("VALIDATION_ERROR", message, 400, details)


class UnauthorizedError(APIError):
    def __init__(self, message="Authentication required", details=None):
        super().__init__("UNAUTHORIZED", message, 401, details)


class ForbiddenError(APIError):
    def __init__(self, message="Access denied", details=None):
        super().__init__("FORBIDDEN", message, 403, details)


logger = logging.getLogger(__name__)


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(exc):
        return jsonify(exc.to_dict()), exc.status_code

    @app.errorhandler(400)
    def bad_request(e):
        logger.warning("400 %s %s", request.method, request.path)
        return jsonify({"error": {"code": "BAD_REQUEST", "message": "Bad request"}}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": {"code": "NOT_FOUND", "message": "Not found"}}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": {"code": "METHOD_NOT_ALLOWED", "message": "Method not allowed"}}), 405

    @app.errorhandler(500)
    def internal_error(e):
        logger.error("500 %s %s\n%s", request.method, request.path, traceback.format_exc())
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        tb = traceback.format_exc()
        user_id = getattr(g, "user_id", None)
        logger.error(
            "Unhandled exception: %s %s user=%s\n%s",
            request.method,
            request.path,
            user_id,
            tb,
        )
        if current_app.debug:
            raise e
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}), 500
