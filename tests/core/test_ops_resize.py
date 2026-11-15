"""Resize: units, aspect rules, DPI-only mode and premultiplied alpha."""

from __future__ import annotations

import numpy as np
import pytest

from stickinator.core.ops.base import NeverCancelled, OperationContext
from stickinator.core.ops.resize import (
    DPI_ONLY,
    ResizeParams,
    resize_premultiplied,
    run,
    target_size,
)

CONTEXT = OperationContext(dpi=(300.0, 300.0))


def _canvas(width: int = 100, height: int = 50) -> np.ndarray:
    image = np.zeros((height, width, 4), dtype=np.uint8)
    image[..., 0] = 200
    image[..., 3] = 255
    return image


def test_resizes_in_pixels() -> None:
    result = run(
        _canvas(),
        ResizeParams(width=40, height=20, lock_aspect=False),
        CONTEXT,
        NeverCancelled(),
    )

    assert result.image.shape == (20, 40, 4)
    assert result.dpi == (300.0, 300.0)


def test_inches_convert_using_the_target_dpi() -> None:
    result = run(
        _canvas(),
        ResizeParams(unit="inches", width=2, height=1, dpi=150, lock_aspect=False),
        CONTEXT,
        NeverCancelled(),
    )

    assert result.image.shape == (150, 300, 4)
    assert result.dpi == (150.0, 150.0)


def test_centimetres_convert_to_pixels() -> None:
    params = ResizeParams(unit="cm", width=2.54, height=0, dpi=100, lock_aspect=False)

    assert target_size(100, 50, params) == (100, 50)


def test_lock_aspect_lets_width_win() -> None:
    params = ResizeParams(width=200, height=999, lock_aspect=True)

    assert target_size(100, 50, params) == (200, 100)


def test_lock_aspect_derives_width_from_height() -> None:
    params = ResizeParams(width=0, height=25, lock_aspect=True)

    assert target_size(100, 50, params) == (50, 25)


def test_lock_aspect_requires_one_dimension() -> None:
    with pytest.raises(ValueError, match="Enter a width or a height"):
        target_size(100, 50, ResizeParams(width=0, height=0, lock_aspect=True))


def test_dpi_only_keeps_the_pixels() -> None:
    image = _canvas()

    result = run(image, ResizeParams(mode=DPI_ONLY, dpi=600), CONTEXT, NeverCancelled())

    assert result.image is image
    assert result.dpi == (600.0, 600.0)


def test_same_size_is_a_no_op() -> None:
    image = _canvas(100, 50)

    result = run(
        image,
        ResizeParams(width=100, height=50, lock_aspect=False),
        CONTEXT,
        NeverCancelled(),
    )

    assert result.image is image


def test_downscaling_does_not_darken_semi_transparent_edges() -> None:
    image = np.zeros((1, 2, 4), dtype=np.uint8)
    image[0, 0] = (255, 0, 0, 255)
    image[0, 1] = (0, 0, 0, 0)

    result = run(
        image,
        ResizeParams(width=1, height=1, lock_aspect=False, resampling="bilinear"),
        CONTEXT,
        NeverCancelled(),
    )

    assert result.image.shape == (1, 1, 4)
    assert result.image[0, 0, 0] > 200
    assert 100 <= result.image[0, 0, 3] <= 155


def test_fully_transparent_pixels_stay_transparent() -> None:
    image = np.zeros((4, 4, 4), dtype=np.uint8)

    result = resize_premultiplied(image, 2, 2, "bilinear")

    assert (result[..., 3] == 0).all()
    assert (result[..., :3] == 0).all()


def test_unknown_choices_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown mode"):
        ResizeParams(mode="stretch")
    with pytest.raises(ValueError, match="unknown unit"):
        ResizeParams(unit="furlongs")
    with pytest.raises(ValueError, match="unknown resampling"):
        ResizeParams(resampling="magic")


def test_non_positive_dpi_is_rejected() -> None:
    with pytest.raises(ValueError, match="dpi"):
        ResizeParams(dpi=0)
