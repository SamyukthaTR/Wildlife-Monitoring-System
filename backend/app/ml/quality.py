"""Image quality assessment.

Camera traps fire at night, in rain, and on empty frames, so an identification
is only as trustworthy as the image behind it. These are ordinary image
statistics, not a learned model, and the thresholds below are stated so the
score can be argued with rather than taken on faith.
"""

import numpy as np

# Variance of the Laplacian. Low variance means few sharp edges, i.e. blur.
# 100 is the commonly used cut-off for "acceptably sharp" on 8-bit images.
BLUR_SHARP = 150.0
BLUR_ACCEPTABLE = 60.0

# Mean luminance on 0-255. Outside this band the frame is under/over exposed.
EXPOSURE_LOW = 55.0
EXPOSURE_HIGH = 200.0

# Fraction of pixels crushed to black or blown to white before it matters.
CLIPPING_LIMIT = 0.20

# Standard deviation of luminance. Flat frames carry little information.
CONTRAST_GOOD = 50.0
CONTRAST_LOW = 20.0


def assess(image_rgb: np.ndarray) -> dict:
    """Score an RGB image array from 0 (unusable) to 1 (good).

    Returns the component measurements alongside the score so the UI can explain
    *why* a frame scored badly instead of only showing a number.
    """
    import cv2

    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)

    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    contrast = float(gray.std())
    total = gray.size
    dark_fraction = float((gray < 16).sum() / total)
    bright_fraction = float((gray > 239).sum() / total)

    # Each component contributes 0-1; the score is their weighted mean.
    sharpness_score = _ramp(blur, BLUR_ACCEPTABLE, BLUR_SHARP)
    contrast_score = _ramp(contrast, CONTRAST_LOW, CONTRAST_GOOD)
    exposure_score = _band(brightness, EXPOSURE_LOW, EXPOSURE_HIGH)
    clipping_score = 1.0 - min(1.0, (dark_fraction + bright_fraction) / CLIPPING_LIMIT)
    clipping_score = max(0.0, clipping_score)

    score = (
        0.40 * sharpness_score
        + 0.25 * exposure_score
        + 0.20 * contrast_score
        + 0.15 * clipping_score
    )

    notes = []
    if blur < BLUR_ACCEPTABLE:
        notes.append("blurred or motion-smeared")
    if brightness < EXPOSURE_LOW:
        notes.append("underexposed (low light or night capture)")
    elif brightness > EXPOSURE_HIGH:
        notes.append("overexposed")
    if contrast < CONTRAST_LOW:
        notes.append("low contrast")
    if dark_fraction > CLIPPING_LIMIT:
        notes.append(f"{dark_fraction:.0%} of pixels crushed to black")
    if bright_fraction > CLIPPING_LIMIT:
        notes.append(f"{bright_fraction:.0%} of pixels blown to white")
    if not notes:
        notes.append("no quality issues detected")

    return {
        "score": round(score, 3),
        "notes": "; ".join(notes),
        "blur_laplacian_variance": round(blur, 1),
        "brightness_mean": round(brightness, 1),
        "contrast_std": round(contrast, 1),
        "dark_pixel_fraction": round(dark_fraction, 4),
        "bright_pixel_fraction": round(bright_fraction, 4),
    }


def _ramp(value: float, low: float, high: float) -> float:
    """0 below `low`, 1 above `high`, linear in between."""
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    return (value - low) / (high - low)


def _band(value: float, low: float, high: float) -> float:
    """1 inside [low, high], falling off linearly outside it."""
    if low <= value <= high:
        return 1.0
    if value < low:
        return max(0.0, value / low)
    return max(0.0, 1.0 - (value - high) / (255.0 - high))
