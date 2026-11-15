"""Sticker outline: grow the content mask and fill it with a solid colour."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from stickinator.core.ops.base import (
    CancelToken,
    Operation,
    OperationContext,
    OperationResult,
    Params,
    RGBAImage,
)

CLOSE = "close"
HULL = "hull"
UNITS = frozenset({"px", "inches"})


@dataclass(frozen=True, slots=True)
class BorderParams(Params):
    width: float = 8.0
    unit: str = "px"
    color: tuple[int, int, int] = (255, 255, 255)
    alpha_threshold: int = 128
    outer_outline_only: bool = True
    merge_pieces: bool = True
    merge_method: str = CLOSE
    merge_radius: float = 3.0
    smooth: bool = True
    smoothing: float = 2.0
    solid_alpha: bool = True
    auto_extend: bool = True

    def __post_init__(self) -> None:
        if self.width < 0:
            msg = "width must not be negative"
            raise ValueError(msg)
        if self.unit not in UNITS:
            msg = f"unknown unit: {self.unit}"
            raise ValueError(msg)
        if not 0 <= self.alpha_threshold <= 255:
            msg = "alpha_threshold must be between 0 and 255"
            raise ValueError(msg)
        if self.merge_method not in {CLOSE, HULL}:
            msg = f"unknown merge method: {self.merge_method}"
            raise ValueError(msg)
        if self.merge_radius < 0 or self.smoothing < 0:
            msg = "radius and smoothing must not be negative"
            raise ValueError(msg)
        if len(self.color) != 3 or any(not 0 <= channel <= 255 for channel in self.color):
            msg = "color must be three channels between 0 and 255"
            raise ValueError(msg)


def run(
    image: RGBAImage,
    params: BorderParams,
    context: OperationContext,
    cancel: CancelToken,
) -> OperationResult:
    cancel.raise_if_cancelled()
    width = _width_pixels(params, context)
    sigma = max(0.5, params.smoothing / 2.0)
    growth = width + (sigma if params.smooth else 0.0)

    mask = (image[..., 3] >= params.alpha_threshold).astype(np.uint8)
    if not mask.any():
        return OperationResult(image)

    if params.merge_pieces:
        mask = _merge(mask, params)
    if params.outer_outline_only:
        mask = _fill_holes(mask)
    cancel.raise_if_cancelled()

    margin = int(np.ceil(growth + 3.0 * sigma + 1.0)) if params.auto_extend else 0
    padded_mask = np.pad(mask, margin, mode="constant")
    if growth > 0:
        distance = cv2.distanceTransform(1 - padded_mask, cv2.DIST_L2, 5)
        grown = (distance <= growth).astype(np.uint8)
    else:
        grown = padded_mask
    if params.smooth:
        blurred = cv2.GaussianBlur(grown.astype(np.float32), (0, 0), sigma)
        grown = (blurred >= 0.5).astype(np.uint8)
    cancel.raise_if_cancelled()

    canvas = _composite(image, grown, margin, params)
    if params.solid_alpha:
        canvas[..., 3] = np.where(canvas[..., 3] >= 128, 255, 0).astype(np.uint8)
    return OperationResult(canvas)


def _width_pixels(params: BorderParams, context: OperationContext) -> float:
    if params.unit == "px":
        return params.width
    return params.width * context.dpi[0]


def _merge(mask: np.ndarray, params: BorderParams) -> np.ndarray:
    if params.merge_method == HULL:
        points = cv2.findNonZero(mask)
        if points is None:
            return mask
        hull = cv2.convexHull(points)
        filled = np.zeros_like(mask)
        cv2.fillConvexPoly(filled, hull, 1)
        return filled

    radius = max(1, round(params.merge_radius))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    height, width = mask.shape
    padded = np.pad(mask, 1, mode="constant")
    flood = padded.copy()
    flood_mask = np.zeros((height + 4, width + 4), np.uint8)
    cv2.floodFill(flood, flood_mask, (0, 0), 1)
    holes = (flood[1:-1, 1:-1] == 0) & (mask == 0)
    filled = mask.copy()
    filled[holes] = 1
    return filled


def _composite(
    image: RGBAImage,
    grown: np.ndarray,
    margin: int,
    params: BorderParams,
) -> RGBAImage:
    height, width = image.shape[:2]
    canvas = np.zeros((grown.shape[0], grown.shape[1], 4), dtype=np.uint8)

    border = grown == 1
    canvas[border] = (*params.color, 255)

    region = canvas[margin : margin + height, margin : margin + width]
    source = image.astype(np.float32)
    destination = region.astype(np.float32)
    alpha = source[..., 3:4] / 255.0
    merged = np.empty_like(destination)
    merged[..., :3] = source[..., :3] * alpha + destination[..., :3] * (1.0 - alpha)
    merged[..., 3:4] = source[..., 3:4] + destination[..., 3:4] * (1.0 - alpha)
    region[...] = np.clip(merged, 0, 255).round().astype(np.uint8)
    return canvas


BORDER = Operation(key="border", label="Border", params_type=BorderParams, run=run)
