"""Prometheus metrics primitives and helper wrappers."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# HTTP metrics
http_requests_total = Counter(
    "app_http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
http_request_duration_seconds = Histogram(
    "app_http_request_duration_seconds",
    "HTTP request duration seconds",
    ["method", "path", "status"],
)

# LLM call metrics
llm_calls_total = Counter(
    "app_llm_calls_total", "LLM call count", ["provider", "model", "status"]
)
llm_call_duration_seconds = Histogram(
    "app_llm_call_duration_seconds",
    "LLM call duration seconds",
    ["provider", "model", "status"],
)

# Cache/Redis metrics (hit/miss) to derive hit-rate externally
cache_hits_total = Counter(
    "app_cache_hits_total", "Cache hits", ["cache_name"]
)
cache_misses_total = Counter(
    "app_cache_misses_total", "Cache misses", ["cache_name"]
)

# DB query counter (rough) by source
db_queries_total = Counter(
    "app_db_queries_total", "DB query count", ["source"]
)

# Socket.IO online gauge
socketio_connections = Gauge(
    "app_socketio_connections", "Current Socket.IO connections"
)

# Background sync metrics
sync_duration_seconds = Histogram(
    "app_sync_duration_seconds", "Background sync duration", ["job", "status"]
)
sync_failures_total = Counter(
    "app_sync_failures_total", "Background sync failures", ["job"]
)


def observe_request(method: str, path: str, status: int, latency_seconds: float | None) -> None:
    status_str = str(status)
    http_requests_total.labels(method=method, path=path, status=status_str).inc()
    if latency_seconds is not None:
        http_request_duration_seconds.labels(
            method=method, path=path, status=status_str
        ).observe(max(latency_seconds, 0))


def observe_llm_call(
    provider: str, model: str, status: str, latency_seconds: float | None
) -> None:
    status_norm = status or "unknown"
    llm_calls_total.labels(provider=provider, model=model, status=status_norm).inc()
    if latency_seconds is not None:
        llm_call_duration_seconds.labels(
            provider=provider, model=model, status=status_norm
        ).observe(max(latency_seconds, 0))


def record_cache_hit(cache_name: str) -> None:
    cache_hits_total.labels(cache_name=cache_name).inc()


def record_cache_miss(cache_name: str) -> None:
    cache_misses_total.labels(cache_name=cache_name).inc()


def record_db_query(source: str = "default") -> None:
    db_queries_total.labels(source=source).inc()


def socket_connected() -> None:
    socketio_connections.inc()


def socket_disconnected() -> None:
    socketio_connections.dec()


def observe_sync(job: str, duration_seconds: float, status: str = "success") -> None:
    sync_duration_seconds.labels(job=job, status=status).observe(max(duration_seconds, 0))
    if status != "success":
        sync_failures_total.labels(job=job).inc()
