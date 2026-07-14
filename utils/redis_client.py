"""Redis client helper for pub/sub and caching."""
import json
from typing import Optional

import redis
import config


_redis_client: Optional[redis.Redis] = None


def get_redis() -> Optional[redis.Redis]:
    """Get a singleton Redis client. Returns None if disabled or unreachable."""
    global _redis_client
    if not config.REDIS_ENABLED:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        if config.REDIS_URL:
            client = redis.Redis.from_url(config.REDIS_URL, decode_responses=True)
        else:
            client = redis.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB,
                password=config.REDIS_PASSWORD or None,
                decode_responses=True,
            )
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception as exc:  # noqa: BLE001
        print(f"[redis] unavailable: {exc}")
        _redis_client = None
        return None


def safe_json_dumps(data) -> str:
    try:
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return "{}"


def safe_json_loads(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None


def session_token_key(user_id: str) -> str:
    """Build Redis key for a user's login token."""
    return f"{config.SESSION_TOKEN_PREFIX}:{user_id}"


def persist_session_token(user_id: str, token: str) -> None:
    """Write login token with TTL for single-session control."""
    r = get_redis()
    if not r:
        return
    try:
        r.setex(session_token_key(user_id), config.SESSION_TOKEN_TTL_SECONDS, token)
    except Exception:
        pass


def drop_session_token(user_id: str) -> None:
    """Remove login token to force logout everywhere."""
    r = get_redis()
    if not r:
        return
    try:
        r.delete(session_token_key(user_id))
    except Exception:
        pass


def validate_session_token(user_id: str, token: str, *, refresh_ttl: bool = True) -> tuple[bool, str]:
    """Check whether token matches cache; optionally refresh TTL.

    Returns (ok, reason) where reason is one of: ok, missing, mismatch, redis_disabled.
    """
    r = get_redis()
    if not r:
        return True, "redis_disabled"
    try:
        cached = r.get(session_token_key(user_id))
        if cached is None:
            return False, "missing"
        if cached != token:
            return False, "mismatch"
        if refresh_ttl:
            r.expire(session_token_key(user_id), config.SESSION_TOKEN_TTL_SECONDS)
        return True, "ok"
    except Exception:
        return False, "error"
