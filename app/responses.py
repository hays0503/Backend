from flask import jsonify


def ok(data=None, status_code=200):
    if data is not None:
        return jsonify(data), status_code
    return jsonify({"success": True}), status_code


def error(message, status_code=400):
    return jsonify({"error": message}), status_code
