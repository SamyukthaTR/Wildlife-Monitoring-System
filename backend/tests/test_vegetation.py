"""Tests for vegetation.assess -- synthetic in-memory images, no disk fixtures.

Confirms each metric moves in the expected direction for solid-colour and
high-frequency test patterns, not exact reference values.
"""

import numpy as np

from app.ml.vegetation import assess


def _solid(rgb: tuple[int, int, int], size: int = 60) -> np.ndarray:
    image = np.zeros((size, size, 3), dtype=np.uint8)
    image[:, :] = rgb
    return image


def _checkerboard(size: int = 60, block: int = 4) -> np.ndarray:
    image = np.zeros((size, size, 3), dtype=np.uint8)
    for y in range(0, size, block):
        for x in range(0, size, block):
            if ((x // block) + (y // block)) % 2 == 0:
                image[y:y + block, x:x + block] = (255, 255, 255)
    return image


def test_solid_green_reads_as_high_vegetation():
    result = assess(_solid((0, 255, 0)))
    assert result["vegetation_index"] == 1.0
    assert result["green_pixel_fraction"] == 1.0


def test_solid_brown_reads_as_low_vegetation():
    green = assess(_solid((0, 255, 0)))
    brown = assess(_solid((139, 69, 19)))
    assert brown["vegetation_index"] < green["vegetation_index"]
    assert brown["green_pixel_fraction"] == 0.0


def test_solid_grey_is_neutral_and_greener_than_brown():
    grey = assess(_solid((128, 128, 128)))
    brown = assess(_solid((139, 69, 19)))
    assert grey["green_pixel_fraction"] == 0.0
    assert grey["vegetation_index"] > brown["vegetation_index"]


def test_uniform_image_has_no_texture():
    result = assess(_solid((0, 255, 0)))
    assert result["canopy_texture_index"] == 0.0


def test_checkerboard_has_more_texture_than_uniform():
    flat = assess(_solid((100, 140, 90)))
    busy = assess(_checkerboard())
    assert busy["canopy_texture_index"] > flat["canopy_texture_index"]


def test_scores_are_bounded_0_to_1():
    for rgb in [(0, 0, 0), (255, 255, 255), (0, 255, 0), (255, 0, 0)]:
        result = assess(_solid(rgb))
        assert 0.0 <= result["vegetation_index"] <= 1.0
        assert 0.0 <= result["green_pixel_fraction"] <= 1.0
        assert 0.0 <= result["canopy_texture_index"] <= 1.0
