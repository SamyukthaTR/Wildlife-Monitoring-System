"""Vegetation analysis from real camera-trap image pixels.

No satellite or drone imagery is available to this platform, so vegetation
signal is read directly from the RGB pixels of the same camera-trap photos the
species recognition engine already analyses -- the same "real pixels in, real
number out" precedent as `app/ml/quality.py`'s blur/exposure scoring. These are
ordinary colour-index formulas from the plant-ecology and precision-agriculture
literature, not a learned model, and the thresholds below are stated so the
numbers can be argued with.
"""

import numpy as np

# Excess Green Index over normalised chromaticity coordinates (Woebbecke et al.
# 1995): exg = 2g - r - b, where r,g,b are each channel's share of R+G+B. With
# r+g+b == 1 this reduces to exg = 3g - 1, which ranges over roughly [-1, 2].
# vegetation_index rescales that to [0, 1].
EXG_RANGE = 3.0
EXG_MIN = -1.0

# A pixel counts as "green" once its ExG clears this margin above the
# grey/neutral point (exg == 0), so sun-bleached grass and shadowed leaves
# still register without pure noise pixels being counted.
GREEN_PIXEL_EXG_THRESHOLD = 0.10

# Laplacian variance reference for canopy_texture_index's 0-1 rescale. Not a
# hard ceiling -- a fixed denominator so scores are comparable across images,
# the same role BLUR_SHARP plays in quality.py.
TEXTURE_REFERENCE_VARIANCE = 2000.0


def assess(image_rgb: np.ndarray) -> dict:
    """Score an RGB image array (H, W, 3), uint8, for vegetation and texture.

    `vegetation_index` is how green the frame reads (0 = no green matter
    detected, 1 = dominated by green vegetation). `green_pixel_fraction` is the
    share of pixels that individually clear the green threshold.
    `canopy_texture_index` is edge density from a Laplacian, used as a rough
    proxy for visual clutter -- dense canopy/undergrowth reads high, open
    ground or sky reads low. None of these are a trained classifier.
    """
    import cv2

    img = image_rgb.astype(np.float32)
    total = img.sum(axis=2) + 1e-6  # avoid div-by-zero on pure black pixels
    r = img[..., 0] / total
    g = img[..., 1] / total
    b = img[..., 2] / total

    exg = 2 * g - r - b
    vegetation_index = float(np.clip((exg.mean() - EXG_MIN) / EXG_RANGE, 0.0, 1.0))
    green_pixel_fraction = float((exg > GREEN_PIXEL_EXG_THRESHOLD).mean())

    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    edge_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    canopy_texture_index = float(np.clip(edge_variance / TEXTURE_REFERENCE_VARIANCE, 0.0, 1.0))

    return {
        "vegetation_index": round(vegetation_index, 4),
        "green_pixel_fraction": round(green_pixel_fraction, 4),
        "canopy_texture_index": round(canopy_texture_index, 4),
    }
