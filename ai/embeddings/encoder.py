from __future__ import annotations

import os
from typing import Iterable, Sequence

import numpy as np

from backend.config.settings import settings

# Disable Hugging Face hub network check warnings and telemetry
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

_MODEL = None


def detect_device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def get_embedding_model(model_name: str | None = None):
    """Process-level singleton embedding model.

    Loads the SentenceTransformer model once and caches it in memory.
    Prefers local cached weights to avoid network round-trips to HuggingFace.
    """
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        name = model_name or settings.embedding_model
        device = detect_device()
        try:
            # First attempt: load directly from local cache (instant, no HF network delay)
            _MODEL = SentenceTransformer(name, device=device, local_files_only=True)
        except Exception:
            # Fallback if model not yet cached locally
            _MODEL = SentenceTransformer(name, device=device)
    return _MODEL


# Backward compatibility alias
def get_model(model_name: str | None = None):
    return get_embedding_model(model_name)


class EmbeddingEncoder:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.embedding_model
        self.device = detect_device()

    @property
    def model(self):
        return get_embedding_model(self.model_name)

    def encode(self, texts: Sequence[str], batch_size: int = 32, show_progress: bool = False) -> np.ndarray:
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        vectors = self.model.encode(
            list(texts),
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return np.asarray(vectors, dtype=np.float32)

    def encode_query(self, text: str) -> list[float]:
        vector = self.encode([text], batch_size=1, show_progress=False)
        return vector[0].tolist()

    def encode_batches(
        self,
        texts: Iterable[str],
        batch_size: int = 32,
    ) -> np.ndarray:
        buffer: list[str] = []
        parts: list[np.ndarray] = []
        for text in texts:
            buffer.append(text)
            if len(buffer) >= batch_size:
                parts.append(self.encode(buffer, batch_size=batch_size))
                buffer = []
        if buffer:
            parts.append(self.encode(buffer, batch_size=batch_size))
        if not parts:
            return np.zeros((0, 384), dtype=np.float32)
        return np.vstack(parts)


_encoder: EmbeddingEncoder | None = None


def get_encoder() -> EmbeddingEncoder:
    global _encoder
    if _encoder is None:
        _encoder = EmbeddingEncoder()
    return _encoder
