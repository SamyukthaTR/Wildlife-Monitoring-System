"""Bioacoustic recognition engine.

Pipeline for one recording:
  1. load at 16 kHz mono (what AST expects)
  2. estimate the noise floor from the quietest part of the recording
  3. segment into acoustic events -- stretches loud enough to contain a call
  4. classify each event with AST against the AudioSet ontology
  5. split the labels into biological detections and filtered environmental noise

An honest limitation, surfaced rather than hidden: AudioSet has no species-level
classes. This engine can tell a bird from an insect from rain; it cannot tell a
macaw from a parakeet. Acoustic detections are therefore stored at coarse rank
and excluded from species-level diversity indices.
"""

import time

import numpy as np

from app.core.config import settings
from app.ml import labels as label_maps
from app.ml.registry import AUDIO_MODEL_NAME, get_audio_model

SAMPLE_RATE = 16000
# AST was trained on 10.24 s windows; shorter clips are padded by the extractor.
WINDOW_SECONDS = 10.0
# Analysis frame for the energy envelope.
FRAME_LENGTH = 2048
HOP_LENGTH = 512

# An event starts when short-term energy rises this many dB above the noise
# floor, and ends when it falls back below it.
ONSET_MARGIN_DB = 8.0
# Events shorter than this are transients (a twig, a click), not calls.
MIN_EVENT_SECONDS = 0.35
# Gaps shorter than this are within one call sequence, so the events are merged.
MERGE_GAP_SECONDS = 0.4
# Cap on how many windows we classify, so a long dawn chorus cannot stall a
# request. AST costs a couple of CPU-seconds per window.
MAX_WINDOWS = 6
# AudioSet labels reported per window.
TOP_K = 5


class ModelUnavailable(RuntimeError):
    """Raised when the audio model could not be loaded."""


def analyse_audio(path: str) -> dict:
    """Run the full audio pipeline. Returns a result dict; raises on hard failure."""
    import librosa

    started = time.perf_counter()

    waveform, _ = librosa.load(path, sr=SAMPLE_RATE, mono=True)
    duration = float(len(waveform) / SAMPLE_RATE)

    audio_model = get_audio_model()
    if not audio_model.available:
        raise ModelUnavailable(f"{AUDIO_MODEL_NAME} unavailable: {audio_model.error}")

    events, noise_profile = detect_acoustic_events(waveform)
    windows = _windows_covering(events, duration)

    classifications = []
    for window in windows:
        segment = _extract(waveform, window)
        for label, confidence in _classify_segment(audio_model, segment):
            biological = label_maps.audioset_lookup(label)
            classifications.append({
                "label_raw": label,
                "label_source": AUDIO_MODEL_NAME,
                "confidence": confidence,
                "start_time_s": round(window["start"], 3),
                "end_time_s": round(window["end"], 3),
                "is_noise": biological is None,
                "taxon": biological[0] if biological else None,
                "species_group": biological[1] if biological else None,
            })

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    biological_count = sum(1 for c in classifications if not c["is_noise"])

    return {
        "media_kind": "audio",
        "duration_s": round(duration, 2),
        "sample_rate": SAMPLE_RATE,
        "acoustic_events": len(events),
        "windows_classified": len(windows),
        "biological_detections": biological_count,
        "filtered_noise_labels": len(classifications) - biological_count,
        "noise_profile": noise_profile,
        "classifications": classifications,
        "models_used": AUDIO_MODEL_NAME,
        "latency_ms": elapsed_ms,
        "note": (
            "AudioSet has no species-level classes, so these labels identify a "
            "sound type (bird, insect, frog) rather than a species. They are "
            "stored at coarse rank and excluded from species diversity indices."
        ),
    }


def detect_acoustic_events(waveform: np.ndarray) -> tuple[list[dict], dict]:
    """Segment a waveform into candidate call events.

    The noise floor is taken as the 10th percentile of frame energy, which for
    field recordings is the ambient background between calls. Everything that
    rises clearly above it is a candidate event; everything else is the
    environmental noise the specification asks to filter out.
    """
    import librosa

    if waveform.size == 0:
        return [], {"noise_floor_db": None, "note": "empty recording"}

    rms = librosa.feature.rms(
        y=waveform, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH
    )[0]
    rms_db = librosa.amplitude_to_db(rms, ref=np.max)

    noise_floor_db = float(np.percentile(rms_db, 10))
    threshold_db = noise_floor_db + ONSET_MARGIN_DB

    # Spectral flatness distinguishes tonal calls from broadband hiss: a value
    # near 1 is noise-like, near 0 is tonal. Reported for transparency.
    flatness = float(
        np.mean(librosa.feature.spectral_flatness(y=waveform, hop_length=HOP_LENGTH))
    )

    active = rms_db > threshold_db
    times = librosa.frames_to_time(np.arange(len(rms_db)), sr=SAMPLE_RATE, hop_length=HOP_LENGTH)

    events: list[dict] = []
    start_index = None
    for index, is_active in enumerate(active):
        if is_active and start_index is None:
            start_index = index
        elif not is_active and start_index is not None:
            events.append({"start": float(times[start_index]), "end": float(times[index])})
            start_index = None
    if start_index is not None:
        events.append({"start": float(times[start_index]), "end": float(times[-1])})

    events = _merge_and_filter(events)

    profile = {
        "noise_floor_db": round(noise_floor_db, 2),
        "onset_threshold_db": round(threshold_db, 2),
        "spectral_flatness": round(flatness, 4),
        "note": (
            "Noise floor is the 10th percentile of frame energy. Audio below "
            f"{ONSET_MARGIN_DB:.0f} dB above it is treated as background and not "
            "classified."
        ),
    }
    return events, profile


def _merge_and_filter(events: list[dict]) -> list[dict]:
    """Join events separated by short gaps, then drop the ones too brief to be calls."""
    if not events:
        return []

    merged = [dict(events[0])]
    for event in events[1:]:
        if event["start"] - merged[-1]["end"] <= MERGE_GAP_SECONDS:
            merged[-1]["end"] = event["end"]
        else:
            merged.append(dict(event))

    return [e for e in merged if (e["end"] - e["start"]) >= MIN_EVENT_SECONDS]


def _windows_covering(events: list[dict], duration: float) -> list[dict]:
    """Pick the non-overlapping windows that contain the detected events.

    The recording is tiled into fixed windows of the length AST expects, and
    only tiles containing at least one event are classified.

    Centring a window on each event instead would make consecutive windows
    overlap almost completely on a bird calling every two seconds -- the model
    would be handed near-identical audio repeatedly, returning identical scores
    and multiplying inference cost for no extra information. Tiling classifies
    each second of audio at most once.
    """
    if not events:
        return []

    tiles = {}
    for event in events:
        first = int(event["start"] // WINDOW_SECONDS)
        last = int(event["end"] // WINDOW_SECONDS)
        for index in range(first, last + 1):
            start = index * WINDOW_SECONDS
            if start >= duration:
                continue
            tiles[index] = {"start": start, "end": min(start + WINDOW_SECONDS, duration)}

    ordered = [tiles[key] for key in sorted(tiles)]
    return ordered[:MAX_WINDOWS]


def _extract(waveform: np.ndarray, window: dict) -> np.ndarray:
    """Slice a window out of the waveform, padded to the model's fixed length."""
    window_samples = int(WINDOW_SECONDS * SAMPLE_RATE)
    start = int(window["start"] * SAMPLE_RATE)
    segment = waveform[start:start + window_samples]
    if len(segment) < window_samples:
        segment = np.pad(segment, (0, window_samples - len(segment)))
    return segment


def _classify_segment(audio_model, segment: np.ndarray) -> list[tuple[str, float]]:
    """Top AudioSet labels for one window.

    AST is multi-label (sigmoid), not multi-class: several sounds can be present
    at once, so scores are independent and do not sum to 1.
    """
    import torch

    extractor = audio_model.extra["extractor"]
    id2label = audio_model.extra["id2label"]

    inputs = extractor(segment, sampling_rate=SAMPLE_RATE, return_tensors="pt")
    with torch.no_grad():
        logits = audio_model.model(**inputs).logits[0]
    scores = torch.sigmoid(logits)

    top_scores, top_indices = scores.topk(TOP_K)
    results = []
    for score, index in zip(top_scores.tolist(), top_indices.tolist()):
        if score < settings.AUDIO_CONF_THRESHOLD:
            continue
        results.append((id2label[index], round(float(score), 4)))
    return results
