"""Wildlife image analysis engine.

Pipeline for one image:
  1. load and measure quality
  2. YOLOv8n detects animals -> bounding boxes and a count
  3. ResNet-50 classifies each detected animal -> a species-level label
  4. if the detector found nothing, classify the whole frame once, so an animal
     COCO has no class for (an insect, a fish) can still be identified

Confidence below the configured threshold is recorded as an unknown detection
rather than dropped: "an animal is here and I cannot name it" is a real and
useful result for a wildlife survey.
"""

import time

import numpy as np
from PIL import Image

from app.core.config import settings
from app.ml import labels as label_maps
from app.ml import quality
from app.ml.registry import CLASSIFIER_NAME, DETECTOR_NAME, get_classifier, get_detector

# Boxes narrower than this fraction of the frame are usually detector noise on
# camera-trap vegetation.
MIN_BOX_FRACTION = 0.0005

# Aspect-ratio cut-offs for the posture hint. Geometric only.
UPRIGHT_RATIO = 1.25
PRONE_RATIO = 0.80


class ModelUnavailable(RuntimeError):
    """Raised when a required model could not be loaded."""


def analyse_image(path: str) -> dict:
    """Run the full image pipeline. Returns a result dict; raises on hard failure."""
    started = time.perf_counter()

    with Image.open(path) as img:
        img = img.convert("RGB")
        rgb = np.array(img)
    height, width = rgb.shape[:2]

    quality_result = quality.assess(rgb)

    detector = get_detector()
    if not detector.available:
        raise ModelUnavailable(f"{DETECTOR_NAME} unavailable: {detector.error}")
    classifier = get_classifier()
    if not classifier.available:
        raise ModelUnavailable(f"{CLASSIFIER_NAME} unavailable: {classifier.error}")

    boxes = _detect_animals(detector, rgb, width, height)

    detections = []
    if boxes:
        for index, box in enumerate(boxes):
            crop = _crop(rgb, box)
            identification = _classify(classifier, crop)
            detections.append(_build_detection(index, box, identification))
    else:
        # No localised animal. Classify the frame as a whole -- this is how
        # insects, fish and anything else outside COCO's ten classes get named.
        identification = _classify(classifier, rgb)
        if identification and identification["confidence"] >= settings.CLASSIFICATION_CONF_THRESHOLD:
            detections.append(_build_detection(0, None, identification))

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    return {
        "media_kind": "image",
        "width": width,
        "height": height,
        "animal_count": len(boxes),
        "quality": quality_result,
        "detections": detections,
        "models_used": f"{DETECTOR_NAME}+{CLASSIFIER_NAME}",
        "latency_ms": elapsed_ms,
        "note": (
            "animal_count is the number of localised animals in this frame. "
            "Detections without a bounding box came from whole-frame "
            "classification after the detector found nothing."
        ),
    }


def _detect_animals(detector, rgb: np.ndarray, width: int, height: int) -> list[dict]:
    """YOLOv8 boxes, filtered to COCO's animal classes."""
    results = detector.model.predict(
        rgb, conf=settings.DETECTION_CONF_THRESHOLD, verbose=False
    )
    class_names = detector.extra["class_names"]
    frame_area = float(width * height)

    boxes = []
    for result in results:
        for box in result.boxes:
            name = class_names[int(box.cls.item())]
            if name not in label_maps.COCO_ANIMAL_CLASSES:
                continue
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
            w, h = x2 - x1, y2 - y1
            if w <= 0 or h <= 0 or (w * h) / frame_area < MIN_BOX_FRACTION:
                continue
            boxes.append({
                "x": max(0, int(round(x1))),
                "y": max(0, int(round(y1))),
                "w": min(width, int(round(w))),
                "h": min(height, int(round(h))),
                "detector_label": name,
                "detector_confidence": round(float(box.conf.item()), 4),
            })

    boxes.sort(key=lambda b: b["detector_confidence"], reverse=True)
    return boxes


def _crop(rgb: np.ndarray, box: dict) -> np.ndarray:
    """Crop with a small margin -- tight boxes cut off the context the
    classifier needs (horns, tails, legs)."""
    height, width = rgb.shape[:2]
    margin_x = int(box["w"] * 0.10)
    margin_y = int(box["h"] * 0.10)
    x1 = max(0, box["x"] - margin_x)
    y1 = max(0, box["y"] - margin_y)
    x2 = min(width, box["x"] + box["w"] + margin_x)
    y2 = min(height, box["y"] + box["h"] + margin_y)
    crop = rgb[y1:y2, x1:x2]
    return crop if crop.size else rgb


def _classify(classifier, rgb: np.ndarray) -> dict | None:
    """Top ImageNet animal class for an RGB array, with its softmax confidence."""
    import torch

    preprocess = classifier.extra["preprocess"]
    categories = classifier.extra["categories"]

    tensor = preprocess(Image.fromarray(rgb)).unsqueeze(0)
    with torch.no_grad():
        probabilities = classifier.model(tensor).softmax(dim=1)[0]

    # Only animal classes are candidates; a wildlife image classified as
    # "flagpole" tells us the classifier failed, not that a flagpole is present.
    top_probs, top_indices = probabilities.topk(10)
    for probability, index in zip(top_probs.tolist(), top_indices.tolist()):
        group = label_maps.imagenet_group_for_index(index)
        if group is None:
            continue
        label = categories[index]
        return {
            "label": label,
            "confidence": round(float(probability), 4),
            "group": group,
            "imagenet_index": index,
            "is_domestic_breed": label_maps.imagenet_is_domestic(label),
        }
    return None


UNIDENTIFIED = "unidentified animal"


def _build_detection(index: int, box: dict | None, identification: dict | None) -> dict:
    """Assemble one detection row's worth of data.

    The important rule here: when the classifier is not confident, the platform
    records "unidentified animal" -- not the detector's COCO guess. YOLO trained
    on COCO calls a snapping turtle an "elephant" and a salamander a "bird" with
    high objectness, because it is matching shape against ten animal classes
    that do not include either. Presenting that as the finding would be wrong in
    a way a surveyor could not detect.

    The detector's class and the classifier's best guess are both kept, so the
    result reads "unidentified animal, closest match terrapin (18%)" rather than
    silently discarding the evidence.
    """
    confident = (
        identification is not None
        and identification["confidence"] >= settings.CLASSIFICATION_CONF_THRESHOLD
        and not identification["is_domestic_breed"]
    )

    if confident:
        label = identification["label"]
        source = CLASSIFIER_NAME
        confidence = identification["confidence"]
        group = identification["group"]
    elif box is not None:
        # An animal was localised but not named. Confidence describes what we do
        # know: that something animal-shaped is present.
        label = UNIDENTIFIED
        source = DETECTOR_NAME
        confidence = box["detector_confidence"]
        group = None
    else:
        label = UNIDENTIFIED
        source = CLASSIFIER_NAME
        confidence = identification["confidence"] if identification else 0.0
        group = None

    detection = {
        "detection_index": index,
        "label_raw": label,
        "label_source": source,
        "confidence": confidence,
        "species_group": group,
        "is_unknown": not confident,
        "bbox": box and {"x": box["x"], "y": box["y"], "w": box["w"], "h": box["h"]},
        "posture_hint": _posture_hint(box),
        "detector_label": box["detector_label"] if box else None,
        "candidate_label": identification["label"] if identification else None,
        "candidate_confidence": identification["confidence"] if identification else None,
    }
    if identification and not confident:
        detection["rejection_reason"] = (
            "domestic breed label" if identification["is_domestic_breed"]
            else f"below confidence threshold {settings.CLASSIFICATION_CONF_THRESHOLD}"
        )
    return detection


def _posture_hint(box: dict | None) -> str | None:
    """Coarse posture from the box aspect ratio.

    This is geometry, not behaviour recognition. It is labelled as a heuristic
    everywhere it surfaces, because a trained behaviour classifier would need a
    behaviour-annotated dataset the platform does not have.
    """
    if not box or not box["h"]:
        return None
    ratio = box["h"] / box["w"] if box["w"] else 0
    if ratio >= UPRIGHT_RATIO:
        return "upright (taller than wide)"
    if ratio <= PRONE_RATIO:
        return "horizontal (wider than tall)"
    return "square-ish"
