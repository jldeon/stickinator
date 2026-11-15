"""Grow the canvas with transparent pixels; never scale or crop."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from stickinator.core.ops.base import (
    CancelToken,
    Operation,
    OperationContext,
    OperationResult,
    Params,
    RGBAImage,
)

UNIFORM = "uniform"
PER_SIDE = "per_side"
UNITS = frozenset({"px", "percent", "inches"})


@dataclass(frozen=True, slots=True)
class ExtendCanvasParams(Params):
    mode: str = UNIFORM
    unit: str = "px"
    amount: float = 0.0
    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    keep_centered: bool = True

    def __post_init__(self) -> None:
        if self.mode not in {UNIFORM, PER_SIDE}:
            msg = f"unknown mode: {self.mode}"
            raise ValueError(msg)
        if self.unit not in UNITS:
            msg = f"unknown unit: {self.unit}"
            raise ValueError(msg)


def run(
    image: RGBAImage,
    params: ExtendCanvasParams,
    context: OperationContext,
    cancel: CancelToken,
) -> OperationResult:
    cancel.raise_if_cancelled()
    height, width = image.shape[:2]
    left, top, right, bottom = margins(width, height, params, context)
    if not any((left, top, right, bottom)):
        return OperationResult(image)

    result = np.zeros((height + top + bottom, width + left + right, 4), dtype=np.uint8)
    result[top : top + height, left : left + width] = image
    return OperationResult(result)


def margins(
    width: int,
    height: int,
    params: ExtendCanvasParams,
    context: OperationContext,
) -> tuple[int, int, int, int]:
    """Margins in pixels as ``(left, top, right, bottom)``."""
    x_dpi, y_dpi = context.dpi

    if params.mode == UNIFORM:
        horizontal = _to_pixels(params.amount, params.unit, x_dpi, width)
        vertical = _to_pixels(params.amount, params.unit, y_dpi, height)
        return horizontal, vertical, horizontal, vertical

    left = _to_pixels(params.left, params.unit, x_dpi, width)
    right = _to_pixels(params.right, params.unit, x_dpi, width)
    top = _to_pixels(params.top, params.unit, y_dpi, height)
    bottom = _to_pixels(params.bottom, params.unit, y_dpi, height)

    if params.keep_centered:
        horizontal = max(left, right)
        vertical = max(top, bottom)
        left = right = horizontal
        top = bottom = vertical

    return left, top, right, bottom


def _to_pixels(value: float, unit: str, dpi: float, reference: int) -> int:
    if unit == "px":
        pixels = value
    elif unit == "percent":
        pixels = reference * value / 100.0
    else:
        pixels = value * dpi
    return max(0, round(pixels))


EXTEND_CANVAS = Operation(
    key="extend_canvas",
    label="Extend Canvas",
    params_type=ExtendCanvasParams,
    run=run,
)
