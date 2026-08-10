"""Lazy, thread-safe model loading.

Nothing here loads at import time. The API process, alembic and the seed scripts
all import this module's package transitively, and none of them should pay for
(or fail on) a 350 MB weight download.

A model that fails to load is remembered as unavailable along with the reason,
so the analysis pipeline can record an honest `failed` run with a readable error
instead of raising a 500 on every request.
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

DETECTOR_NAME = "yolov8n-coco"
CLASSIFIER_NAME = "resnet50-imagenet"
AUDIO_MODEL_NAME = "ast-audioset"

# HuggingFace id for the Audio Spectrogram Transformer fine-tuned on AudioSet.
# Same 527-label ontology as YAMNet, but PyTorch, so the whole stack stays on
# one framework.
AST_CHECKPOINT = "MIT/ast-finetuned-audioset-10-10-0.4593"


@dataclass
class LoadedModel:
    name: str
    model: Any = None
    extra: dict = field(default_factory=dict)
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.model is not None


_lock = threading.Lock()
_cache: dict[str, LoadedModel] = {}


def _load_once(key: str, loader) -> LoadedModel:
    """Run `loader` at most once per process, caching success and failure alike."""
    cached = _cache.get(key)
    if cached is not None:
        return cached

    with _lock:
        # Re-check: another thread may have loaded it while we waited.
        cached = _cache.get(key)
        if cached is not None:
            return cached

        if not settings.ENABLE_ML:
            result = LoadedModel(name=key, error="ML is disabled (ENABLE_ML=false)")
        else:
            try:
                logger.info("Loading model %s ...", key)
                result = loader()
                logger.info("Model %s ready", key)
            except Exception as exc:  # noqa: BLE001 - degrade, never crash the API
                logger.warning("Model %s unavailable: %s", key, exc)
                result = LoadedModel(name=key, error=f"{type(exc).__name__}: {exc}")

        _cache[key] = result
        return result


def _load_detector() -> LoadedModel:
    from ultralytics import YOLO

    # Ultralytics downloads yolov8n.pt on first use into YOLO_CONFIG_DIR.
    model = YOLO("yolov8n.pt")
    return LoadedModel(name=DETECTOR_NAME, model=model, extra={"class_names": model.names})


def _load_classifier() -> LoadedModel:
    import torch
    from torchvision.models import ResNet50_Weights, resnet50

    weights = ResNet50_Weights.IMAGENET1K_V2
    model = resnet50(weights=weights)
    model.eval()
    torch.set_num_threads(2)
    return LoadedModel(
        name=CLASSIFIER_NAME,
        model=model,
        extra={"preprocess": weights.transforms(), "categories": weights.meta["categories"]},
    )


def _load_audio_model() -> LoadedModel:
    import torch
    from transformers import ASTFeatureExtractor, ASTForAudioClassification

    extractor = ASTFeatureExtractor.from_pretrained(AST_CHECKPOINT)
    model = ASTForAudioClassification.from_pretrained(AST_CHECKPOINT)
    model.eval()
    torch.set_num_threads(2)
    return LoadedModel(
        name=AUDIO_MODEL_NAME,
        model=model,
        extra={"extractor": extractor, "id2label": model.config.id2label},
    )


def get_detector() -> LoadedModel:
    return _load_once(DETECTOR_NAME, _load_detector)


def get_classifier() -> LoadedModel:
    return _load_once(CLASSIFIER_NAME, _load_classifier)


def get_audio_model() -> LoadedModel:
    return _load_once(AUDIO_MODEL_NAME, _load_audio_model)


def status() -> dict:
    """Report which models are loaded, without triggering a load."""
    return {
        "enabled": settings.ENABLE_ML,
        "models": {
            name: {
                "loaded": entry.available,
                "error": entry.error,
            }
            for name, entry in _cache.items()
        },
    }
