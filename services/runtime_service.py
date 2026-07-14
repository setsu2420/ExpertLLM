"""Runtime background tasks: Redis pub/sub forwarder and DB→Redis sync."""
from __future__ import annotations

import threading
import time

import config
from utils.redis_client import get_redis, safe_json_loads
from services.user_service import user_service
from services import metrics


def start_pubsub_forwarder(socketio) -> None:
    """Forward Redis pub/sub messages to Socket.IO rooms."""
    def _worker():
        backoff = 1
        while True:
            r = get_redis()
            if not r:
                time.sleep(min(backoff, 60))
                backoff = min(backoff * 2, 60)
                continue
            try:
                pubsub = r.pubsub()
                pubsub.psubscribe(f"{config.REDIS_PUBLIC_CHANNEL_PREFIX}:*")
                for message in pubsub.listen():
                    if message is None:
                        continue
                    if message.get('type') not in ('message', 'pmessage'):
                        continue
                    channel = message.get('channel') or ''
                    data = safe_json_loads(message.get('data') or '')
                    if not data:
                        continue
                    action = data.get('action')
                    payload = data.get('message')
                    if not payload:
                        continue
                    try:
                        profession = channel.split(':')[-1]
                        room = user_service.get_major_room(profession)
                        if not room:
                            continue
                        if action == 'create':
                            socketio.emit('public:new_message', payload, room=room)
                        elif action == 'vote':
                            socketio.emit('public:vote', payload, room=room)
                    except Exception:
                        continue
                backoff = 1
            except Exception as e:
                try:
                    print(f"[PubSub] forwarder error: {e}; reconnecting in {backoff}s")
                except Exception:
                    pass
                time.sleep(min(backoff, 60))
                backoff = min(backoff * 2, 60)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def sync_db_to_redis() -> None:
    """Load public messages from DB into Redis cache."""
    r = get_redis()
    if not r:
        print("[Sync] Redis not available, skipping sync")
        return

    start = time.time()
    status = "success"
    try:
        from routes.public_routes import _cache_messages
        import db_service

        deleted = 0
        for pattern in (f"{config.REDIS_PUBLIC_LIST_PREFIX}:*", f"{config.REDIS_PUBLIC_HASH_PREFIX}:*"):
            batch: list[str] = []
            for k in r.scan_iter(match=pattern, count=1000):
                batch.append(k)
                if len(batch) >= 500:
                    r.delete(*batch)
                    deleted += len(batch)
                    batch.clear()
            if batch:
                r.delete(*batch)
                deleted += len(batch)
                batch.clear()
        if deleted:
            print(f"[Sync] Cleared {deleted} old Redis keys")

        messages = db_service.list_public_messages(
            limit=500,
            user_id=None,
            user_profession=None,
            start_utc=None,
            end_utc=None
        )
        if messages:
            _cache_messages(messages)
            print(f"[Sync] Synced {len(messages)} messages to Redis")
        else:
            print("[Sync] No messages to sync")
    except Exception as e:
        status = "failure"
        print(f"[Sync] Error syncing to Redis: {e}")
    finally:
        metrics.observe_sync(
            job="db_to_redis",
            duration_seconds=time.time() - start,
            status=status,
        )


def start_periodic_sync(app) -> None:
    """Start periodic DB→Redis sync every 2 hours.

    The semantic question trending job is now handled by a dedicated
    runner process (see question_trending_runner.py) and is no longer
    invoked from this in-app background thread.
    """
    def _sync_worker():
        while True:
            try:
                time.sleep(2 * 60 * 60)
                print("[Sync] Starting periodic DB→Redis sync...")
                with app.app_context():
                    sync_db_to_redis()
            except Exception as e:
                print(f"[Sync] Periodic sync error: {e}")
                metrics.observe_sync(
                    job="periodic_sync_loop",
                    duration_seconds=0,
                    status="failure",
                )

    t = threading.Thread(target=_sync_worker, daemon=True)
    t.start()
    print("[Sync] Periodic sync task started (every 2 hours)")
