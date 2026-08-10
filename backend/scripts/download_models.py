"""Pre-download the model weights and check the engines can load.

Run once after building the image:
    docker compose exec backend python -m scripts.download_models

Weights land in MODEL_CACHE_DIR, which docker-compose backs with the
wildlife_models volume, so they survive rebuilds and are fetched only once.

Without this, the first analysis request pays for a ~450 MB download and looks
like a hang. Running it here also turns a network failure into a clear message
now rather than a failed analysis run later.
"""

import sys

from app.core.config import settings
from app.ml.registry import (
    AST_CHECKPOINT,
    AUDIO_MODEL_NAME,
    CLASSIFIER_NAME,
    DETECTOR_NAME,
    get_audio_model,
    get_classifier,
    get_detector,
)

MODELS = [
    (DETECTOR_NAME, "animal detection / bounding boxes", get_detector, "~6 MB"),
    (CLASSIFIER_NAME, "species classification", get_classifier, "~100 MB"),
    (AUDIO_MODEL_NAME, f"bioacoustics ({AST_CHECKPOINT})", get_audio_model, "~350 MB"),
]


def main() -> int:
    if not settings.ENABLE_ML:
        print("ENABLE_ML is false; nothing to download.")
        return 0

    print(f"Model cache: {settings.MODEL_CACHE_DIR}\n")
    failures = []

    for name, purpose, loader, size in MODELS:
        print(f"{name} -- {purpose} ({size})")
        loaded = loader()
        if loaded.available:
            print("  ready\n")
        else:
            print(f"  FAILED: {loaded.error}\n")
            failures.append((name, loaded.error))

    if failures:
        print(f"{len(failures)} of {len(MODELS)} model(s) unavailable:")
        for name, error in failures:
            print(f"  - {name}: {error}")
        print(
            "\nAnalysis will record these as failed runs with the error above "
            "rather than returning a server error. Re-run once the download can "
            "succeed."
        )
        return 1

    print("All models ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
