"""公共聊天路由 - Redis + 专业内聚"""
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, session

import db_service
import config
from services.user_service import user_service
from services import metrics
from utils.decorators import login_required
from utils.redis_client import get_redis, safe_json_dumps, safe_json_loads

public_bp = Blueprint('public', __name__, url_prefix='/api/public')


# Redis key helpers
def _list_key(profession: str) -> str:
    return f"{config.REDIS_PUBLIC_LIST_PREFIX}:{profession}"


def _hash_key(message_id: str) -> str:
    return f"{config.REDIS_PUBLIC_HASH_PREFIX}:{message_id}"


def _channel(profession: str) -> str:
    return f"{config.REDIS_PUBLIC_CHANNEL_PREFIX}:{profession}"


def _cache_messages(messages: List[Dict]) -> None:
    """Cache messages to Redis list + hash; ignore errors."""
    if not messages:
        return
    r = get_redis()
    if not r:
        return
    by_prof: Dict[str, List[Dict]] = {}
    for msg in messages:
        prof = msg.get("profession") or ""
        if not prof:
            continue
        by_prof.setdefault(prof, []).append(msg)

    pipe = r.pipeline()
    for prof, items in by_prof.items():
        list_key = _list_key(prof)
        for msg in items:
            mid = msg.get("message_id")
            if not mid:
                continue
            # 写哈希并设置 TTL（单条消息）
            hash_key = _hash_key(mid)
            pipe.hset(hash_key, mapping={"data": safe_json_dumps(msg)})
            pipe.expire(hash_key, config.REDIS_PUBLIC_TTL_SECONDS)
            # 去重后追加到列表，并设置列表 TTL
            pipe.lrem(list_key, 0, mid)
            pipe.rpush(list_key, mid)
        pipe.ltrim(list_key, -config.REDIS_PUBLIC_LIST_MAX, -1)
        pipe.expire(list_key, config.REDIS_PUBLIC_TTL_SECONDS)
    try:
        pipe.execute()
    except Exception:
        pass


def _get_cached_messages(profession: str, limit: int) -> Optional[List[Dict]]:
    r = get_redis()
    if not r:
        return None
    try:
        ids = r.lrange(_list_key(profession), -limit, -1)
        if not ids:
            metrics.record_cache_miss("public_messages")
            return []
        # 防御性去重，保持顺序
        seen = set()
        uniq_ids: List[str] = []
        for mid in ids:
            if mid not in seen:
                seen.add(mid)
                uniq_ids.append(mid)
        pipe = r.pipeline()
        for mid in uniq_ids:
            pipe.hget(_hash_key(mid), "data")
        raw_list = pipe.execute()
        msgs: List[Dict] = []
        for raw in raw_list:
            msg = safe_json_loads(raw) if raw else None
            if msg:
                msgs.append(msg)
        if msgs:
            metrics.record_cache_hit("public_messages")
        else:
            metrics.record_cache_miss("public_messages")
        return msgs
    except Exception:
        return None


def _publish_to_channel(profession: str, payload: Dict) -> None:
    r = get_redis()
    if not r:
        return
    try:
        r.publish(_channel(profession), safe_json_dumps(payload))
    except Exception:
        pass


def _update_cached_message(msg: Dict) -> None:
    """Update only the hash for a single message to avoid list duplicates."""
    if not msg:
        return
    r = get_redis()
    if not r:
        return
    mid = msg.get("message_id")
    if not mid:
        return
    try:
        r.hset(_hash_key(mid), mapping={"data": safe_json_dumps(msg)})
    except Exception:
        pass


@public_bp.route("/messages", methods=["GET"])
@login_required
def list_public_messages():
    """获取当前用户专业的公屏消息（Redis 优先，DB 回源）"""
    current_user_id = session.get('user_id')
    _, user_profession = user_service.get_user_and_profession(current_user_id)
    if not user_profession:
        return jsonify({"status": "error", "content": "User not found"}), 404

    # 仅展示当天消息（UTC 0 点到次日 0 点）
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    def _within_today(msg: Dict) -> bool:
        ts = msg.get("created_at_iso") or msg.get("created_at")
        if not ts:
            return False
        try:
            if isinstance(ts, str) and ts.endswith('Z'):
                ts = ts[:-1]
            if isinstance(ts, str):
                try:
                    dt = datetime.fromisoformat(ts)
                except ValueError:
                    dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            else:
                return False
            return today_start <= dt < today_end
        except Exception:
            return False

    try:
        limit = int(request.args.get("limit", "200") or 200)
    except ValueError:
        limit = 200
    limit = max(1, min(limit, 500))

    # 先尝试 Redis
    cached = _get_cached_messages(user_profession, limit)
    if cached is not None:
        filtered = [m for m in cached if _within_today(m)]
        # 确保按 created_at 升序
        cached_sorted = sorted(
            filtered,
            key=lambda x: x.get("created_at_iso") or x.get("created_at") or "",
        )
        return jsonify({"status": "success", "messages": cached_sorted})

    # 回源 DB，并回填缓存
    try:
        messages = db_service.list_public_messages(
            limit=limit,
            user_id=current_user_id,
            user_profession=user_profession,
            start_utc=today_start,
            end_utc=today_end,
        )
        _cache_messages(messages)
        return jsonify({"status": "success", "messages": messages})
    except Exception as e:  # noqa: BLE001
        return jsonify({"status": "error", "content": str(e)}), 400


@public_bp.route("/messages", methods=["POST"])
@login_required
def create_public_message():
    """发布公共消息，并写入 Redis + 广播频道"""
    current_user_id = session.get('user_id')
    _, user_profession = user_service.get_user_and_profession(current_user_id)
    if not user_profession:
        return jsonify({"status": "error", "content": "User not found"}), 404

    data = request.json or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"status": "error", "content": "Content is empty"}), 400

    try:
        msg = db_service.create_public_message(current_user_id, content, user_profession)
        _cache_messages([msg])
        _publish_to_channel(user_profession, {"action": "create", "message": msg})
        # pub/sub forwarder will emit to room, no need to emit here
        return jsonify({"status": "success", "message": msg})
    except Exception as e:  # noqa: BLE001
        return jsonify({"status": "error", "content": str(e)}), 400


@public_bp.route("/vote", methods=["POST"])
@login_required
def vote_public_message():
    """投票公屏消息，同专业校验 + Redis 更新"""
    current_user_id = session.get('user_id')
    _, user_profession = user_service.get_user_and_profession(current_user_id)
    if not user_profession:
        return jsonify({"status": "error", "content": "User not found"}), 404

    data = request.json or {}
    message_id = (data.get("message_id") or "").strip()
    vote = (data.get("vote") or "").strip().lower()
    if not message_id or vote not in {"like", "dislike"}:
        return jsonify({"status": "error", "content": "Missing message_id or invalid vote"}), 400

    try:
        msg = db_service.vote_public_message(
            current_user_id, message_id, vote, user_profession
        )
        # 更新哈希避免重复追加到列表
        _update_cached_message(msg)
        _publish_to_channel(user_profession, {"action": "vote", "message": msg})
        # pub/sub forwarder will emit to room, no need to emit here
        return jsonify({"status": "success", "message": msg})
    except Exception as e:  # noqa: BLE001
        return jsonify({"status": "error", "content": str(e)}), 400
