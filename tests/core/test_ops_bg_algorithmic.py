"""Algorithmic background removal: colour key, tolerance, seeds and GrabCut."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from stickinator.core.ops.base import NeverCancelled, OperationContext
from stickinator.core.ops.bg_algorithmic import (
    CONTIGUOUS,
    GLOBAL,
    GRABCUT,
    PICKED,
    BgRemovalParams,
    dominant_edge_colour,
    run,
)

CONTEXT = OperationContext()
BACKGROUND = (240, 240, 240)
SUBJECT = (200, 40, 40)


def _canvas(width: int = 100, height: int = 100) -> np.ndarray:
    image = np.zeros((height, width, 4), dtype=np.uint8)
    image[...] = (*BACKGROUND, 255)
    return image


def _paint(image: np.ndarray, ys: slice, xs: slice, colour: tuple[int, int, int]) -> None:
    image[ys, xs] = (*colour, 255)


def _iou(image: np.ndarray, expected: np.ndarray) -> float:
    actual = image[..., 3] > 127
    union = np.logical_or(actual, expected).sum()
    if union == 0:
        return 1.0
    return float(np.logical_and(actual, expected).sum() / union)


def test_removes_background_when_the_subject_is_inside() -> None:
    image = _canvas()
    _paint(image, slice(30, 70), slice(30, 70), SUBJECT)
    expected = image[..., 3] > 0
    expected[:] = False
    expected[30:70, 30:70] = True

    result = run(
        image,
        BgRemovalParams(tolerance=10.0, mode=CONTIGUOUS),
        CONTEXT,
        NeverCancelled(),
    )

    assert _iou(result.image, expected) >= 0.98
    assert result.image[0, 0, 3] == 0
    assert result.image[50, 50, 3] == 255


def test_works_when_the_subject_touches_one_edge() -> None:
    image = _canvas()
    _paint(image, slice(30, 70), slice(0, 40), SUBJECT)

    result = run(image, BgRemovalParams(tolerance=10.0), CONTEXT, NeverCancelled())

    assert result.image[50, 20, 3] == 255
    assert result.image[50, 80, 3] == 0
    assert result.image[10, 10, 3] == 0


def test_works_when_the_subject_touches_two_edges() -> None:
    image = _canvas()
    _paint(image, slice(0, 40), slice(0, 40), SUBJECT)

    result = run(image, BgRemovalParams(tolerance=10.0), CONTEXT, NeverCancelled())

    assert result.image[20, 20, 3] == 255
    assert result.image[0, 0, 3] == 255
    assert result.image[80, 80, 3] == 0


def test_enclosed_background_needs_a_seed_or_global_mode() -> None:
    image = _canvas()
    image[...] = (*SUBJECT, 255)
    _paint(image, slice(20, 80), slice(20, 80), BACKGROUND)

    # Auto edge detection would sample the subject here, so the background has
    # to be picked explicitly once it no longer touches an edge.
    with pytest.raises(ValueError, match="does not touch the image edge"):
        run(
            image,
            BgRemovalParams(
                tolerance=10.0,
                mode=CONTIGUOUS,
                color_source=PICKED,
                color=BACKGROUND,
            ),
            CONTEXT,
            NeverCancelled(),
        )

    global_result = run(
        image,
        BgRemovalParams(tolerance=10.0, mode=GLOBAL, color_source=PICKED, color=BACKGROUND),
        CONTEXT,
        NeverCancelled(),
    )
    assert global_result.image[50, 50, 3] == 0
    assert global_result.image[0, 0, 3] == 255

    seeded = run(
        image,
        BgRemovalParams(
            tolerance=10.0,
            mode=CONTIGUOUS,
            color_source=PICKED,
            color=BACKGROUND,
            seed_x=50,
            seed_y=50,
        ),
        CONTEXT,
        NeverCancelled(),
    )
    assert seeded.image[50, 50, 3] == 0
    assert seeded.image[0, 0, 3] == 255


def test_seed_removes_a_hole_inside_the_subject() -> None:
    image = _canvas()
    _paint(image, slice(20, 80), slice(20, 80), SUBJECT)
    _paint(image, slice(45, 55), slice(45, 55), BACKGROUND)

    result = run(
        image,
        BgRemovalParams(
            mode=CONTIGUOUS,
            color_source=PICKED,
            color=BACKGROUND,
            seed_x=50,
            seed_y=50,
        ),
        CONTEXT,
        NeverCancelled(),
    )

    assert result.image[50, 50, 3] == 0
    assert result.image[25, 25, 3] == 255
    assert result.image[0, 0, 3] == 0


def test_tolerance_controls_how_far_colours_are_removed() -> None:
    image = _canvas()
    _paint(image, slice(0, 50), slice(0, 50), (230, 230, 230))
    _paint(image, slice(50, 100), slice(50, 100), SUBJECT)

    tight = run(image, BgRemovalParams(tolerance=2.0), CONTEXT, NeverCancelled())
    loose = run(image, BgRemovalParams(tolerance=10.0), CONTEXT, NeverCancelled())

    assert tight.image[10, 10, 3] == 255  # ~4.7 deltaE away from the background
    assert loose.image[10, 10, 3] == 0
    assert loose.image[80, 80, 3] == 255


def test_feather_produces_soft_alpha() -> None:
    image = _canvas()
    _paint(image, slice(30, 70), slice(30, 70), SUBJECT)

    hard = run(image, BgRemovalParams(tolerance=10.0), CONTEXT, NeverCancelled())
    soft = run(image, BgRemovalParams(tolerance=10.0, feather=6.0), CONTEXT, NeverCancelled())

    assert set(np.unique(hard.image[..., 3]).tolist()) <= {0, 255}
    values = set(np.unique(soft.image[..., 3]).tolist())
    assert any(0 < value < 255 for value in values)


def test_despeckle_removes_small_islands() -> None:
    image = _canvas()
    _paint(image, slice(30, 70), slice(30, 70), SUBJECT)
    _paint(image, slice(10, 13), slice(10, 13), SUBJECT)

    kept = run(image, BgRemovalParams(tolerance=10.0), CONTEXT, NeverCancelled())
    cleaned = run(image, BgRemovalParams(tolerance=10.0, despeckle=50), CONTEXT, NeverCancelled())

    assert kept.image[11, 11, 3] == 255
    assert cleaned.image[11, 11, 3] == 0
    assert cleaned.image[50, 50, 3] == 255


def test_dominant_edge_colour_finds_the_border_colour() -> None:
    image = _canvas()
    _paint(image, slice(30, 70), slice(30, 70), SUBJECT)

    assert dominant_edge_colour(image) == BACKGROUND


def test_grabcut_separates_a_contrasting_subject() -> None:
    image = _canvas(120, 120)
    _paint(image, slice(30, 90), slice(30, 90), SUBJECT)
    expected = np.zeros((120, 120), dtype=bool)
    expected[30:90, 30:90] = True

    result = run(
        image,
        BgRemovalParams(method=GRABCUT, inset=5.0, iterations=5),
        CONTEXT,
        NeverCancelled(),
    )

    assert _iou(result.image, expected) >= 0.9
    assert result.image[0, 0, 3] == 0
    assert result.image[60, 60, 3] == 255


def test_seed_outside_the_background_colour_is_reported() -> None:
    image = _canvas()
    _paint(image, slice(30, 70), slice(30, 70), SUBJECT)

    with pytest.raises(ValueError, match="picked point does not match"):
        run(
            image,
            BgRemovalParams(color_source=PICKED, color=BACKGROUND, seed_x=50, seed_y=50),
            CONTEXT,
            NeverCancelled(),
        )


def test_seed_outside_the_image_is_reported() -> None:
    image = _canvas()

    with pytest.raises(ValueError, match="outside the image"):
        run(
            image,
            BgRemovalParams(color_source=PICKED, color=BACKGROUND, seed_x=500, seed_y=0),
            CONTEXT,
            NeverCancelled(),
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"method": "magic"}, "unknown method"),
        ({"color_source": "sampled"}, "unknown colour source"),
        ({"mode": "local"}, "unknown mode"),
        ({"inset_unit": "mm"}, "unknown inset unit"),
        ({"tolerance": -1}, "tolerance"),
        ({"feather": -1}, "feather"),
        ({"despeckle": -1}, "despeckle"),
        ({"iterations": 0}, "iterations"),
        ({"inset": -1}, "inset"),
        ({"color": (1, 2)}, "color"),
    ],
)
def test_invalid_params_are_rejected(kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        BgRemovalParams(**kwargs)
