from __future__ import annotations

from ai.embeddings.encoder import detect_device


def test_device_detection_returns_cpu_or_cuda():
    device = detect_device()
    assert device in {"cpu", "cuda"}
