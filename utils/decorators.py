"""装饰器 - 认证等"""
from functools import wraps
from flask import session, jsonify
import logging

from services.admin_service import admin_service
from utils.redis_client import validate_session_token


auth_logger = logging.getLogger("auth")


def _ensure_active_session():
    current_user_id = session.get('user_id')
    token = session.get('login_token')
    if not current_user_id or not token:
        session.clear()
        return None, "missing_session"
    ok, reason = validate_session_token(current_user_id, token, refresh_ttl=True)
    if not ok:
        session.clear()
        auth_logger.info(
            "session_invalid",
            extra={"extra_fields": {"user_id": current_user_id, "reason": reason}},
        )
        return None, reason
    return current_user_id, "ok"

def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user_id, _ = _ensure_active_session()
        if not current_user_id:
            return jsonify({"status": "error", "content": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """管理员权限验证装饰器（需已登录且具备管理员身份）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user_id, _ = _ensure_active_session()
        if not current_user_id:
            return jsonify({"status": "error", "content": "Unauthorized"}), 401
        if not admin_service.is_admin(current_user_id):
            return jsonify({"status": "error", "content": "Admin required"}), 403
        return f(*args, **kwargs)
    return decorated_function
