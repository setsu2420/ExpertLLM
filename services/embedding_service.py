"""Embedding service with pluggable backends (local sentence-transformers or SiliconFlow API)."""
from __future__ import annotations

from typing import List
import json
import time

import numpy as np
import requests

import config


class EmbeddingService:
    def __init__(self) -> None:
        self.backend = (config.EMBEDDING_BACKEND or "silicon").lower()
        self._model = None

    def _ensure_local_model(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception as e:  # pragma: no cover - optional dependency
            raise RuntimeError("sentence-transformers is not installed") from e
        self._model = SentenceTransformer(config.EMBEDDING_LOCAL_MODEL)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        texts = [t.strip() for t in texts if t and t.strip()]
        if not texts:
            return []
        if self.backend == "local":
            return self._embed_local(texts)
        return self._embed_silicon(texts)

    def _embed_local(self, texts: List[str]) -> List[List[float]]:
        import logging
        logger = logging.getLogger("embedding")
        logger.info(f"[embed_local] 输入文本数: {len(texts)}")
        self._ensure_local_model()
        assert self._model is not None
        try:
            vectors = self._model.encode(texts, batch_size=32, convert_to_numpy=True, show_progress_bar=False)
            logger.info(f"[embed_local] 输出向量 shape: {vectors.shape if hasattr(vectors, 'shape') else type(vectors)}")
            return [v.astype(float).tolist() for v in vectors]
        except Exception as e:
            logger.error(f"[embed_local] 发生异常: {e}", exc_info=True)
            raise

    def _embed_silicon(self, texts: List[str]) -> List[List[float]]:
        import logging
        logger = logging.getLogger("embedding")
        logger.info(f"[embed_silicon] 输入文本数: {len(texts)}")
        if not config.SILICON_KEY:
            logger.error("[embed_silicon] SILICON_KEY 未配置")
            raise RuntimeError("SILICON_KEY is not configured")
        model = config.SILICON_EMBEDDING_MODEL or "BAAI/bge-m3"
        base_url = (config.SILICON_URL or "https://api.siliconflow.cn/v1").rstrip("/")
        if "/chat/completions" in base_url:
            base_url = base_url.split("/chat/completions", 1)[0].rstrip("/")
        url = base_url + "/embeddings"
        headers = {"Authorization": f"Bearer {config.SILICON_KEY}", "Content-Type": "application/json"}
        payload = {"model": model, "input": texts}
        backoff = 1.0
        for attempt in range(3):
            try:
                logger.info(f"[embed_silicon] 第{attempt+1}次请求: url={url}, model={model}")
                resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
                if resp.status_code != 200:
                    logger.error(f"[embed_silicon] SiliconFlow error {resp.status_code}: {resp.text}")
                    raise RuntimeError(f"SiliconFlow error {resp.status_code}: {resp.text}")
                data = resp.json()
                embeddings = data.get("data") or []
                logger.info(f"[embed_silicon] 返回向量数: {len(embeddings)}")
                return [item.get("embedding", []) for item in embeddings]
            except Exception as e:
                logger.error(f"[embed_silicon] 发生异常: {e}", exc_info=True)
                time.sleep(backoff)
                backoff *= 2
        logger.error("[embed_silicon] SiliconFlow embedding failed after retries")
        raise RuntimeError("SiliconFlow embedding failed after retries")


embedding_service = EmbeddingService()
