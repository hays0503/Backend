import logging

from flask import jsonify, request


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        logging.warning(f"400: {request.path}")
        return jsonify({"error": "Bad request"}), 400

    @app.errorhandler(404)
    def not_found(e):
        logging.warning(f"404: {request.path}")
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        logging.error(f"500: {request.path}")
        return jsonify({"error": "Internal server error"}), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        import logging
        logging.exception("Unhandled exception")
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred"
            }
        }), 500
