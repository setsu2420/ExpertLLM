"""Flask 应用入口文件"""
from flask import Flask, render_template, session, request, jsonify, g, Response
from flask_socketio import SocketIO, join_room
import threading
import time
import logging
import os

import config
from models import init_app, db
from utils.redis_client import get_redis, safe_json_loads, validate_session_token
from services.user_service import user_service
from services.runtime_service import start_pubsub_forwarder, sync_db_to_redis, start_periodic_sync
from services import metrics
from utils.logging_config import setup_json_logging

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

# 初始化日志（stdout JSON）
access_logger = setup_json_logging(level="INFO")

# 创建 Flask 应用
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = config.SQLALCHEMY_TRACK_MODIFICATIONS
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = config.SQLALCHEMY_ENGINE_OPTIONS
app.secret_key = config.SECRET_KEY

# 初始化数据库
init_app(app)

# 初始化 SocketIO（自动检测最佳异步模式；容器中将选用 eventlet）
socketio = SocketIO(app, cors_allowed_origins="*")

# 运行时任务已迁移至 services.runtime_service

# 创建数据库表和后台任务，仅在未显式禁用引导时运行
if os.getenv("DISABLE_APP_BOOTSTRAP", "").lower() not in {"1", "true", "yes"}:
    with app.app_context():
        db.create_all()

        # 启动时同步数据库到Redis
        print("[Sync] Initial sync: loading data from DB to Redis...")
        sync_db_to_redis()

        # 启动pub/sub转发
        start_pubsub_forwarder(socketio)

        # 启动定期同步任务
        start_periodic_sync(app)

# =================== 日志中间件 ===================
@app.before_request
def _log_request_start():
    g.start_time = time.time()


@app.after_request
def _log_request_end(response):
    try:
        latency_ms = None
        latency_s = None
        if hasattr(g, "start_time"):
            delta = time.time() - g.start_time
            latency_ms = int(delta * 1000)
            latency_s = delta
        access_logger.info(
            "access",
            extra={"extra_fields": {
                "path": request.path,
                "method": request.method,
                "status": response.status_code,
                "latency_ms": latency_ms,
                "user_id": session.get("user_id"),
                "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
            }}
        )
        metrics.observe_request(
            method=request.method,
            path=request.path,
            status=response.status_code,
            latency_seconds=latency_s,
        )
    except Exception:
        pass
    return response


@app.errorhandler(Exception)
def _handle_exception(e):
    # 捕获带有请求上下文和堆栈跟踪信息的未捕获异常
    logging.getLogger("error").error(
        "unhandled_exception",
        extra={"extra_fields": {
            "path": request.path,
            "method": request.method,
            "user_id": session.get("user_id"),
        }},
        exc_info=True,
    )
    return jsonify({"status": "error", "content": "Internal server error"}), 500


@app.route("/metrics")
def metrics_endpoint():
    """Expose Prometheus metrics snapshot."""

    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

# 验证配置
config.validate_config()

# 注册蓝图（路由）

from routes.auth_routes import auth_bp
from routes.llm_chat_routes import chat_bp
from routes.history_routes import history_bp
from routes.public_routes import public_bp
from routes.trending_routes import trending_bp
from routes.question_trending_routes import question_trending_bp
from routes.admin_routes import admin_bp
from routes.user_routes import user_bp

app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(history_bp)
app.register_blueprint(public_bp)
app.register_blueprint(trending_bp)
app.register_blueprint(question_trending_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(user_bp)
# 开发专用路由已移除：不再注册 dev_bp

# =================== 主页路由 ===================
@app.route("/")
def index():
    """首页"""
    current_user_id = session.get('user_id')
    return render_template("index.html", current_user_id=current_user_id)


# =================== WebSocket 事件 ===================
@socketio.on("connect")
def ws_connect(auth=None):
    """WebSocket 连接"""
    uid = session.get("user_id")
    # 当启用 SECURE_SOCKETS 时，禁止通过 auth 传入 user_id；仅允许基于会话的认证
    if not uid and not config.SECURE_SOCKETS and isinstance(auth, dict):
        uid = (auth.get("user_id") or "").strip()
    if not uid:
        return False

    token = session.get("login_token")
    if not token:
        return False
    ok, _ = validate_session_token(uid, token, refresh_ttl=True)
    if not ok:
        return False
    
    user, profession = user_service.get_user_and_profession(uid)
    if not user:
        return False
    
    room = user_service.get_major_room(profession)
    if room:
        join_room(room)
    metrics.socket_connected()
    
    # 仅回发给当前连接的客户端
    socketio.emit("public:joined", {"profession": profession}, to=request.sid)


@socketio.on("disconnect")
def ws_disconnect():
    """WebSocket 断开连接"""
    metrics.socket_disconnected()


# =================== 启动应用 ===================
if __name__ == "__main__":
    socketio.run(
        app,
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )

