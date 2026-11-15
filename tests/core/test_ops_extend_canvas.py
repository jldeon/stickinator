"""Extend canvas: margins in px, percent and inches."""

from __future__ import annotations

import numpy as np
import pytest

from stickinator.core.ops.base import NeverCancelled, OperationContext
from stickinator.core.ops.extend_canvas import (
    PER_SIDE,
    UNIFORM,
    ExtendCanvasParams,
    run,
)

CONTEXT = OperationContext(dpi=(300.0, 300.0))


def _canvas(width: int = 100, height: int = 200) -> np.ndarray:
    image = np.zeros((height, width, 4), dtype=np.uint8)
    image[..., 1] = 200
    image[..., 3] = 255
    return image


def test_uniform_pixels_center_the_content() -> None:
    result = run(_canvas(), ExtendCanvasParams(amount=10), CONTEXT, NeverCancelled())

    assert result.image.shape == (220, 120, 4)
    assert (result.image[0, 0] == 0).all()
    assert result.image[10, 10, 1] == 200
    assert (result.image[-1, -1] == 0).all()


def test_per_side_margins_are_independent() -> None:
    params = ExtendCanvasParams(
        mode=PER_SIDE, left=1, top=2, right=3, bottom=4, keep_centered=False
    )

    result = run(_canvas(10, 20), params, CONTEXT, NeverCancelled())

    assert result.image.shape == (20 + 2 + 4, 10 + 1 + 3, 4)
    assert result.image[2, 1, 1] == 200


def test_keep_centered_symmetrises_per_side_margins() -> None:
    params = ExtendCanvasParams(mode=PER_SIDE, left=1, top=0, right=9, bottom=4, keep_centered=True)

    result = run(_canvas(10, 20), params, CONTEXT, NeverCancelled())

    # 9 px on both horizontal sides, 4 px on both vertical sides.
    assert result.image.shape == (20 + 8, 10 + 18, 4)
    assert result.image[4, 9, 1] == 200


def test_percent_uses_each_axis_dimension() -> None:
    result = run(
        _canvas(100, 200),
        ExtendCanvasParams(amount=50, unit="percent"),
        CONTEXT,
        NeverCancelled(),
    )

    assert result.image.shape == (200 + 200, 100 + 100, 4)


def test_inches_use_the_document_dpi() -> None:
    result = run(
        _canvas(100, 200),
        ExtendCanvasParams(amount=0.5, unit="inches"),
        CONTEXT,
        NeverCancelled(),
    )

    assert result.image.shape == (200 + 300, 100 + 300, 4)


def test_zero_margin_returns_the_same_pixels() -> None:
    image = _canvas()

    result = run(image, ExtendCanvasParams(amount=0), CONTEXT, NeverCancelled())

    assert result.image is image


def test_unknown_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown mode"):
        ExtendCanvasParams(mode="diagonal")


def test_uniform_ignores_per_side_fields() -> None:
    params = ExtendCanvasParams(mode=UNIFORM, amount=5, left=100, top=100)

    result = run(_canvas(10, 10), params, CONTEXT, NeverCancelled())

    assert result.image.shape == (20, 20, 4)
