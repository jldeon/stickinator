"""Border: width accuracy, hole filling, merging and solid alpha."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
import pytest

from stickinator.core.ops.base import NeverCancelled, OperationContext
from stickinator.core.ops.border import (
    CLOSE,
    HULL,
    BorderParams,
    run,
)

CONTEXT = OperationContext(dpi=(300.0, 300.0))
NO_FRILLS: dict[str, Any] = {
    "smooth": False,
    "merge_pieces": False,
    "auto_extend": False,
    "solid_alpha": False,
}


def _square(size: int = 100, start: int = 40, end: int = 60) -> np.ndarray:
    image = np.zeros((size, size, 4), dtype=np.uint8)
    image[start:end, start:end] = (10, 20, 30, 255)
    return image


def _row_width(image: np.ndarray, row: int) -> int:
    return int((image[row, :, 3] > 0).sum())


def _components(image: np.ndarray) -> int:
    count, _ = cv2.connectedComponents((image[..., 3] > 0).astype(np.uint8))
    return count - 1


def test_border_width_is_accurate() -> None:
    result = run(
        _square(),
        BorderParams(width=10, outer_outline_only=False, **NO_FRILLS),
        CONTEXT,
        NeverCancelled(),
    )

    assert result.image.shape == (100, 100, 4)
    assert 39 <= _row_width(result.image, 50) <= 41


def test_smoothed_border_keeps_its_width() -> None:
    result = run(
        _square(),
        BorderParams(
            width=10,
            outer_outline_only=False,
            smooth=True,
            smoothing=2,
            merge_pieces=False,
            auto_extend=False,
            solid_alpha=False,
        ),
        CONTEXT,
        NeverCancelled(),
    )

    assert 38 <= _row_width(result.image, 50) <= 42


def test_auto_extend_keeps_the_border_inside_the_canvas() -> None:
    result = run(
        _square(size=100, start=0, end=20),
        BorderParams(
            width=10,
            outer_outline_only=False,
            smooth=False,
            merge_pieces=False,
            auto_extend=True,
            solid_alpha=False,
        ),
        CONTEXT,
        NeverCancelled(),
    )

    assert result.image.shape[0] > 100
    assert result.image.shape[1] > 100
    # Nothing is clipped: the outer edge of the canvas is still empty.
    assert (result.image[0, :, 3] == 0).all()
    assert (result.image[:, 0, 3] == 0).all()
    assert (result.image[-1, :, 3] == 0).all()
    assert (result.image[:, -1, 3] == 0).all()
    # The full border is present around the content.
    assert 39 <= _row_width(result.image, 20) <= 41


def test_outer_outline_fills_holes_with_the_border_colour() -> None:
    image = np.zeros((100, 100, 4), dtype=np.uint8)
    image[20:80, 20:80] = (10, 20, 30, 255)
    image[35:65, 35:65] = (0, 0, 0, 0)
    params = BorderParams(
        width=5,
        outer_outline_only=True,
        smooth=False,
        merge_pieces=False,
        auto_extend=False,
        solid_alpha=False,
        color=(255, 0, 0),
    )

    result = run(image, params, CONTEXT, NeverCancelled())

    centre = result.image[50, 50]
    assert tuple(centre) == (255, 0, 0, 255)


def test_holes_stay_transparent_without_outer_outline() -> None:
    image = np.zeros((100, 100, 4), dtype=np.uint8)
    image[20:80, 20:80] = (10, 20, 30, 255)
    image[35:65, 35:65] = (0, 0, 0, 0)
    params = BorderParams(
        width=5,
        outer_outline_only=False,
        smooth=False,
        merge_pieces=False,
        auto_extend=False,
        solid_alpha=False,
    )

    result = run(image, params, CONTEXT, NeverCancelled())

    assert result.image[50, 50, 3] == 0


def test_solid_alpha_binarises_every_pixel() -> None:
    result = run(
        _square(),
        BorderParams(width=4, outer_outline_only=False, solid_alpha=True),
        CONTEXT,
        NeverCancelled(),
    )

    assert set(np.unique(result.image[..., 3]).tolist()) <= {0, 255}


def test_merge_closes_the_gap_between_pieces() -> None:
    image = np.zeros((100, 100, 4), dtype=np.uint8)
    image[20:30, 20:30] = (10, 20, 30, 255)
    image[20:30, 40:50] = (10, 20, 30, 255)

    merged = run(
        image,
        BorderParams(
            width=2,
            merge_pieces=True,
            merge_method=CLOSE,
            merge_radius=6,
            smooth=False,
            auto_extend=False,
            solid_alpha=True,
        ),
        CONTEXT,
        NeverCancelled(),
    )
    separate = run(
        image,
        BorderParams(width=2, merge_pieces=False, smooth=False, auto_extend=False),
        CONTEXT,
        NeverCancelled(),
    )

    assert _components(merged.image) == 1
    assert _components(separate.image) == 2


def test_hull_merge_bridges_diagonal_pieces() -> None:
    image = np.zeros((100, 100, 4), dtype=np.uint8)
    image[20:30, 20:30] = (10, 20, 30, 255)
    image[60:70, 60:70] = (10, 20, 30, 255)

    result = run(
        image,
        BorderParams(
            width=1,
            merge_pieces=True,
            merge_method=HULL,
            smooth=False,
            auto_extend=False,
            solid_alpha=True,
        ),
        CONTEXT,
        NeverCancelled(),
    )

    assert result.image[45, 45, 3] == 255
    assert _components(result.image) == 1


def test_fully_transparent_image_is_untouched() -> None:
    image = np.zeros((20, 20, 4), dtype=np.uint8)

    result = run(image, BorderParams(), CONTEXT, NeverCancelled())

    assert result.image is image


def test_inches_use_the_document_dpi() -> None:
    result = run(
        _square(),
        BorderParams(
            width=0.05,  # 15 px at 300 dpi
            unit="inches",
            outer_outline_only=False,
            **NO_FRILLS,
        ),
        CONTEXT,
        NeverCancelled(),
    )

    assert 49 <= _row_width(result.image, 50) <= 51


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"width": -1}, "width"),
        ({"unit": "cm"}, "unknown unit"),
        ({"alpha_threshold": 300}, "alpha_threshold"),
        ({"merge_method": "blur"}, "unknown merge method"),
        ({"color": (1, 2)}, "color"),
    ],
)
def test_invalid_params_are_rejected(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        BorderParams(**kwargs)  # type: ignore[arg-type]
