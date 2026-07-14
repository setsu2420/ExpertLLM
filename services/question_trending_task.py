"""Background task to build semantic question trending clusters and store top results in Redis."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

import numpy as np
from sqlalchemy import or_

import config
from models import db, Session, Turn, QuestionEmbedding
from services.embedding_service import embedding_service
from utils.redis_client import get_redis


STATE_KEY_LAST_CREATED_AT = "question_trending:last_created_at"  # legacy, kept for backward compatibility
STATE_KEY_LAST_TURN_ID = "question_trending:last_turn_id"
REDIS_TOP_KEY = "question_trending_top"


def _hash_prompt(user_id: str, prompt: str) -> str:
    h = hashlib.sha256()
    h.update((user_id or "").encode("utf-8"))
    h.update(b"|")
    h.update((prompt or "").encode("utf-8"))
    return h.hexdigest()


def _load_last_created_at(r) -> datetime | None:
    if not r:
        return None
    value = r.get(STATE_KEY_LAST_CREATED_AT)
    if not value:
        return None
    try:
        # stored as ISO string
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _store_last_created_at(r, dt: datetime | None) -> None:
    if not r or not dt:
        return
    try:
        r.set(STATE_KEY_LAST_CREATED_AT, dt.isoformat())
    except Exception:
        pass


def _load_last_turn_id(r) -> int | None:
    if not r:
        return None
    value = r.get(STATE_KEY_LAST_TURN_ID)
    if not value:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _store_last_turn_id(r, last_id: int | None) -> None:
    if not r or last_id is None:
        return
    try:
        r.set(STATE_KEY_LAST_TURN_ID, str(last_id))
    except Exception:
        pass


def _query_new_prompts(
    last_turn_id: int | None,
    last_created_at: datetime | None,
) -> Tuple[List[Tuple[str, str, datetime]], int | None, datetime | None]:
    """Return new turns since the last cursor.

    We combine two增量条件：
      - 自增主键 `Turn.id` > last_turn_id
      - 或创建时间 `Turn.created_at` > last_created_at

    这样即便发生自增重置或历史游标不一致，也能通过时间维度兜底，避免漏数。
    返回值： (rows, max_turn_id, max_created_at)
    """
    q = db.session.query(Session.user_id, Turn.prompt, Turn.created_at, Turn.id).join(
        Turn, Turn.session_id_fk == Session.id
    ).filter(
        Turn.prompt.isnot(None),
        Turn.prompt != "",
    )

    conds = []
    if last_turn_id is not None:
        conds.append(Turn.id > last_turn_id)
    if last_created_at is not None:
        conds.append(Turn.created_at > last_created_at)
    if conds:
        q = q.filter(or_(*conds))

    rows = q.order_by(Turn.id.asc()).all()

    result: List[Tuple[str, str, datetime]] = []
    max_id: int | None = None
    max_created: datetime | None = None
    for user_id, prompt, created_at, turn_id in rows:
        if not prompt:
            continue
        result.append((user_id or "", prompt, created_at))
        max_id = turn_id
        if created_at is not None and (
            max_created is None or created_at > max_created
        ):
            max_created = created_at
    return result, max_id, max_created


def _upsert_embeddings(rows: List[Tuple[str, str, datetime]]) -> datetime | None:
    """Compute embeddings for new prompts and insert into QuestionEmbedding.

    Returns max created_at seen (for state update).
    """
    if not rows:
        return None
    max_created_at: datetime | None = None
    batch_texts: List[str] = []
    batch_meta: List[Tuple[str, str, datetime]] = []

    def flush_batch() -> None:
        nonlocal max_created_at
        if not batch_texts:
            return
        vectors = embedding_service.embed_texts(batch_texts)
        if not vectors:
            batch_texts.clear()
            batch_meta.clear()
            return
        for (user_id, prompt, created_at), vec in zip(batch_meta, vectors):
            ph = _hash_prompt(user_id, prompt)
            existing = QuestionEmbedding.query.filter_by(prompt_hash=ph).first()
            if existing:
                continue
            arr = np.asarray(vec, dtype=np.float32)
            qe = QuestionEmbedding(
                user_id=user_id,
                prompt=prompt,
                prompt_hash=ph,
                embedding=arr.tobytes(),
                turn_created_at=created_at,
            )
            db.session.add(qe)
            if max_created_at is None or (created_at and created_at > max_created_at):
                max_created_at = created_at
        db.session.commit()
        batch_texts.clear()
        batch_meta.clear()

    for user_id, prompt, created_at in rows:
        batch_texts.append(prompt)
        batch_meta.append((user_id, prompt, created_at))
        if len(batch_texts) >= 64:
            flush_batch()
    flush_batch()
    return max_created_at


def _load_recent_embeddings() -> Tuple[np.ndarray, List[QuestionEmbedding]]:
    """Load recent N embeddings for clustering."""
    days = max(1, config.QUESTION_EMBEDDING_LOOKBACK_DAYS)
    max_samples = max(1, config.QUESTION_EMBEDDING_MAX_SAMPLES)
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=days)

    q = QuestionEmbedding.query
    q = q.filter(QuestionEmbedding.turn_created_at >= cutoff)
    q = q.order_by(QuestionEmbedding.turn_created_at.desc())
    q = q.limit(max_samples)
    rows: List[QuestionEmbedding] = list(q.all())
    if not rows:
        return np.empty((0, 0), dtype=np.float32), []

    vecs: List[np.ndarray] = []
    for row in rows:
        try:
            arr = np.frombuffer(row.embedding, dtype=np.float32)
            vecs.append(arr)
        except Exception:
            continue
    if not vecs:
        return np.empty((0, 0), dtype=np.float32), []

    X = np.vstack(vecs)
    # normalize
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    X = X / norms
    return X, rows


def _cluster_embeddings(X: np.ndarray, rows: List[QuestionEmbedding]):
    """Greedy clustering based on cosine similarity.

    Returns list of clusters, each cluster is dict with:
      - center_idx
      - member_indices
    """
    if X.shape[0] == 0:
        return []
    sim_threshold = float(config.SIM_THRESHOLD or 0.8)
    clusters = []

    # centers use index of X / rows
    for idx in range(X.shape[0]):
        x = X[idx]
        best_cluster = None
        best_sim = -1.0
        for cl in clusters:
            center_vec = X[cl["center_idx"]]
            sim = float(np.dot(x, center_vec))
            if sim > best_sim:
                best_sim = sim
                best_cluster = cl
        if best_cluster is None or best_sim < sim_threshold:
            clusters.append({"center_idx": idx, "member_indices": [idx]})
        else:
            best_cluster["member_indices"].append(idx)
    return clusters


def _build_top_clusters(X: np.ndarray, rows: List[QuestionEmbedding]):
    from math import exp

    if X.shape[0] == 0:
        return []
    clusters = _cluster_embeddings(X, rows)
    if not clusters:
        print(f"[QuestionTrending] clustering: 0 clusters from {X.shape[0]} embeddings")
        return []

    now_utc = datetime.now(timezone.utc)
    lambda_decay = float(getattr(config, "QUESTION_TRENDING_DECAY", 0.02) or 0.02)
    results = []
    for cl in clusters:
        indices = cl["member_indices"]
        count = len(indices)
        if count == 0:
            continue
        decays = []
        for i in indices:
            row = rows[i]
            t = row.turn_created_at or now_utc
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            hours = max(0.0, (now_utc - t).total_seconds() / 3600.0)
            decays.append(exp(-lambda_decay * hours))
        avg_decay = float(sum(decays) / len(decays)) if decays else 1.0
        score = count * avg_decay
        # pick representative: newest
        rep_idx = max(indices, key=lambda i: (rows[i].turn_created_at or now_utc))
        rep_row = rows[rep_idx]
        example_prompts = [rows[i].prompt for i in indices[:5]]
        results.append({
            "prompt": rep_row.prompt,
            "score": score,
            "count": count,
            "examples": example_prompts,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    top_k = max(1, config.QUESTION_TRENDING_TOP_K)
    top = results[:top_k]
    print(
        f"[QuestionTrending] clustering: {len(clusters)} clusters from {X.shape[0]} embeddings, "
        f"writing top {len(top)} to Redis",
    )
    return top


def _write_top_to_redis(top_clusters) -> None:
    r = get_redis()
    if not r:
        return
    try:
        payload = json.dumps(top_clusters, ensure_ascii=False)
        r.set(REDIS_TOP_KEY, payload)
    except Exception:
        pass


def run_question_trending_job() -> None:
    """Entry for periodic question trending job."""
    start_ts = time.time()

    r = get_redis()
    last_turn_id = _load_last_turn_id(r)
    last_created_at = _load_last_created_at(r)
    print(f"[QuestionTrending] last_turn_id state: {last_turn_id}")
    print(f"[QuestionTrending] last_created_at state: {last_created_at}")

    # 兼容旧版：如果两者都为空，首次全量扫描
    new_rows, max_turn_id, max_created_seen = _query_new_prompts(
        last_turn_id, last_created_at
    )
    
    print(f"[QuestionTrending] fetched {len(new_rows)} new turns for embeddings")
    max_created_at = _upsert_embeddings(new_rows)
    # 更新 turn_id 游标
    if r and max_turn_id is not None:
        _store_last_turn_id(r, max_turn_id)
        print(f"[QuestionTrending] embeddings upserted, new last_turn_id: {max_turn_id}")
    # 同时更新 created_at 游标（取查询阶段看到的最大 created_at，兜底）
    if r and (max_created_seen is not None or max_created_at is not None):
        new_created_cursor = max_created_seen or max_created_at
        _store_last_created_at(r, new_created_cursor)
        print(
            f"[QuestionTrending] embeddings upserted, new last_created_at: "
            f"{new_created_cursor}",
        )

    X, rows = _load_recent_embeddings()
    print(f"[QuestionTrending] loaded {X.shape[0]} embeddings for clustering")
    top_clusters = _build_top_clusters(X, rows)
    _write_top_to_redis(top_clusters)

    # 无论本轮是否有新写入，都显式结束当前事务，避免在 REPEATABLE READ
    # 隔离级别下长时间持有同一个快照，看不到之后插入的 turns。
    try:
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

    elapsed = time.time() - start_ts
    print(
        f"[QuestionTrending] job completed, top_clusters written: {len(top_clusters)}, "
        f"elapsed={elapsed:.2f}s",
    )
