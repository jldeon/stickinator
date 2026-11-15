"""Trim: bounding box, threshold, margins and fully transparent input."""

from __future__ import annotations

import numpy as np
import pytest

from stickinator.core.ops.base import NeverCancelled, OperationContext
from stickinator.core.ops.trim import TrimParams, run

CONTEXT = OperationContext()


def _image_with_block() -> np.ndarray:
    image = np.zeros((20, 30, 4), dtype=np.uint8)
    image[5:15, 10:20] = (10, 20, 30, 255)
    return image


def test_crops_to_the_content() -> None:
    result = run(_image_with_block(), TrimParams(), CONTEXT, NeverCancelled())

    assert result.image.shape == (10, 10, 4)
    assert result.image[0, 0, 0] == 10


def test_margin_expands_and_clamps() -> None:
    result = run(_image_with_block(), TrimParams(margin=3), CONTEXT, NeverCancelled())
    assert result.image.shape == (16, 16, 4)

    edge = _image_with_block()
    edge[0:2, 0:2] = (1, 2, 3, 255)
    result = run(edge, TrimParams(margin=10), CONTEXT, NeverCancelled())
    assert result.image.shape == (20, 30, 4)


def test_threshold_ignores_faint_pixels() -> None:
    image = _image_with_block()
    image[0, 0] = (0, 0, 0, 40)

    faint = run(image, TrimParams(threshold=128), CONTEXT, NeverCancelled())
    included = run(image, TrimParams(threshold=10), CONTEXT, NeverCancelled())

    assert faint.image.shape == (10, 10, 4)
    assert included.image.shape == (15, 20, 4)


def test_fully_transparent_image_is_an_error() -> None:
    with pytest.raises(ValueError, match="completely transparent"):
        run(np.zeros((8, 8, 4), dtype=np.uint8), TrimParams(), CONTEXT, NeverCancelled())


def test_rejects_bad_threshold_and_margin() -> None:
    with pytest.raises(ValueError, match="threshold"):
        TrimParams(threshold=256)
    with pytest.raises(ValueError, match="margin"):
        TrimParams(margin=-1)
