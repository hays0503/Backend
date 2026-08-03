import secrets
import time
import uuid
from functools import wraps
from flask import request, g
import jwt
from .config import Config
from .db import get_db
from .responses import error


def create_access_token(user_id, role):
    now = int(time.time())
    payload = {
        "user_id": user_id,
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "iss": getattr(Config, "JWT_ISSUER", "yescada-core"),
        "aud": getattr(Config, "JWT_AUDIENCE", "yescada-api"),
        "exp": now + Config.ACCESS_TOKEN_EXPIRES_SEC,
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")


def create_refresh_token(user_id, jti=None):
    jti = jti or str(uuid.uuid4())
    now = int(time.time())
    payload = {
        "user_id": user_id,
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "iss": getattr(Config, "JWT_ISSUER", "yescada-core"),
        "aud": getattr(Config, "JWT_AUDIENCE", "yescada-api"),
        "exp": now + Config.REFRESH_TOKEN_EXPIRES_SEC,
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256"), jti


def store_session(jti, user_id, expires_at, token_version=0):
    conn = get_db()
    now = int(time.time())
    conn.execute(
        "INSERT INTO auth_sessions (jti, user_id, token_version, expires_at, revoked_at, created_at) "
        "VALUES (?, ?, ?, ?, NULL, ?)",
        (jti, user_id, token_version, expires_at, now),
    )


def is_session_revoked(jti):
    conn = get_db()
    row = conn.execute(
        "SELECT revoked_at FROM auth_sessions WHERE jti = ?", (jti,)
    ).fetchone()
    if not row:
        return False
    return row[0] is not None


def revoke_session(jti):
    now = int(time.time())
    conn = get_db()
    conn.execute(
        "UPDATE auth_sessions SET revoked_at = ? WHERE jti = ? AND revoked_at IS NULL",
        (now, jti),
    )


def revoke_all_sessions(user_id):
    now = int(time.time())
    conn = get_db()
    conn.execute(
        "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
        (now, user_id),
    )


def decode_token(token, expected_type):
    try:
        payload = jwt.decode(
            token,
            Config.SECRET_KEY,
            algorithms=["HS256"],
            issuer=getattr(Config, "JWT_ISSUER", "yescada-core"),
            audience=getattr(Config, "JWT_AUDIENCE", "yescada-api"),
            leeway=getattr(Config, "JWT_CLOCK_SKEW_SEC", 30),
        )
        if payload.get("type") != expected_type:
            return None
        if expected_type == "refresh" and is_session_revoked(payload.get("jti")):
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def set_auth_cookies(response, access_token, refresh_token):
    secure = getattr(Config, "COOKIE_SECURE", False)
    response.set_cookie(
        Config.ACCESS_COOKIE_NAME,
        access_token,
        max_age=Config.ACCESS_TOKEN_EXPIRES_SEC,
        path=Config.ACCESS_COOKIE_PATH,
        secure=secure,
        httponly=True,
        samesite=Config.COOKIE_SAMESITE_ACCESS,
    )
    response.set_cookie(
        Config.REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=Config.REFRESH_TOKEN_EXPIRES_SEC,
        path=Config.REFRESH_COOKIE_PATH,
        secure=secure,
        httponly=True,
        samesite=Config.COOKIE_SAMESITE_REFRESH,
    )
    return response


def set_csrf_cookie(response, token=None):
    token = token or secrets.token_urlsafe(32)
    response.set_cookie(
        Config.CSRF_COOKIE_NAME,
        token,
        max_age=Config.REFRESH_TOKEN_EXPIRES_SEC,
        path="/",
        secure=getattr(Config, "COOKIE_SECURE", False),
        httponly=False,
        samesite=Config.COOKIE_SAMESITE_ACCESS,
    )
    return response


def clear_auth_cookies(response):
    secure = getattr(Config, "COOKIE_SECURE", False)
    for name, path in (
        (Config.ACCESS_COOKIE_NAME, Config.ACCESS_COOKIE_PATH),
        (Config.REFRESH_COOKIE_NAME, Config.REFRESH_COOKIE_PATH),
        (Config.CSRF_COOKIE_NAME, "/"),
    ):
        response.set_cookie(
            name,
            "",
            expires=0,
            max_age=0,
            path=path,
            secure=secure,
            httponly=name != Config.CSRF_COOKIE_NAME,
            samesite=Config.COOKIE_SAMESITE_ACCESS,
        )
    return response


def access_token_from_cookie():
    return request.cookies.get(Config.ACCESS_COOKIE_NAME)


def resolve_access_payload():
    """Return (payload, via) preferring Bearer header, then access cookie."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        payload = decode_token(auth[7:], "access")
        if payload:
            return payload, "bearer"
    cookie = access_token_from_cookie()
    if cookie:
        payload = decode_token(cookie, "access")
        if payload:
            return payload, "cookie"
    return None, None


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        payload, via = resolve_access_payload()
        if not payload:
            return error("Invalid or expired token", 401)
        g.user_id = payload["user_id"]
        g.user_role = payload["role"]
        g.auth_via = via
        return f(*args, **kwargs)

    return wrapper


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if getattr(g, "user_role", None) != "admin":
            return error("Admin only", 403)
        return f(*args, **kwargs)

    return wrapper
