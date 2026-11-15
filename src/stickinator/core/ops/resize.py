"""Change pixel dimensions and print resolution, with premultiplied resampling."""

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

RESIZE = "resize"
DPI_ONLY = "dpi_only"
UNITS = frozenset({"px", "inches", "cm"})
RESAMPLING = {
    "nearest": cv2.INTER_NEAREST,
    "bilinear": cv2.INTER_LINEAR,
    "bicubic": cv2.INTER_CUBIC,
    "lanczos": cv2.INTER_LANCZOS4,
}


@dataclass(frozen=True, slots=True)
class ResizeParams(Params):
    mode: str = RESIZE
    unit: str = "px"
    width: float = 0.0
    height: float = 0.0
    dpi: float = 300.0
    lock_aspect: bool = True
    resampling: str = "lanczos"

    def __post_init__(self) -> None:
        if self.mode not in {RESIZE, DPI_ONLY}:
            msg = f"unknown mode: {self.mode}"
            raise ValueError(msg)
        if self.unit not in UNITS:
            msg = f"unknown unit: {self.unit}"
            raise ValueError(msg)
        if self.resampling not in RESAMPLING:
            msg = f"unknown resampling method: {self.resampling}"
            raise ValueError(msg)
        if self.dpi <= 0:
            msg = "dpi must be positive"
            raise ValueError(msg)
        if self.width < 0 or self.height < 0:
            msg = "width and height must not be negative"
            raise ValueError(msg)


def run(
    image: RGBAImage,
    params: ResizeParams,
    context: OperationContext,
    cancel: CancelToken,
) -> OperationResult:
    cancel.raise_if_cancelled()
    target_dpi = (params.dpi, params.dpi)

    if params.mode == DPI_ONLY:
        return OperationResult(image, dpi=target_dpi)

    height, width = image.shape[:2]
    target_width, target_height = target_size(width, height, params)
    cancel.raise_if_cancelled()

    if (target_width, target_height) == (width, height):
        return OperationResult(image, dpi=target_dpi)

    resized = resize_premultiplied(image, target_width, target_height, params.resampling)
    cancel.raise_if_cancelled()
    return OperationResult(resized, dpi=target_dpi)


def target_size(width: int, height: int, params: ResizeParams) -> tuple[int, int]:
    """Pixel size implied by the requested units and aspect-ratio rule."""
    if params.unit == "px":
        wanted_width = params.width
        wanted_height = params.height
    elif params.unit == "inches":
        wanted_width = params.width * params.dpi
        wanted_height = params.height * params.dpi
    else:
        wanted_width = params.width / 2.54 * params.dpi
        wanted_height = params.height / 2.54 * params.dpi

    if params.lock_aspect:
        # Width wins when both axes are supplied (PLAN.md section 7.6).
        if wanted_width > 0:
            wanted_height = height * (wanted_width / width)
        elif wanted_height > 0:
            wanted_width = width * (wanted_height / height)
        else:
            msg = "Enter a width or a height."
            raise ValueError(msg)
    else:
        if wanted_width <= 0:
            wanted_width = width
        if wanted_height <= 0:
            wanted_height = height

    return max(1, round(wanted_width)), max(1, round(wanted_height))


def resize_premultiplied(
    image: RGBAImage,
    width: int,
    height: int,
    resampling: str = "lanczos",
) -> RGBAImage:
    """Resize colour premultiplied by alpha so edges do not darken."""
    interpolation = RESAMPLING[resampling]
    rgb = image[..., :3].astype(np.float32)
    alpha = image[..., 3].astype(np.float32) / 255.0
    premultiplied = rgb * alpha[..., None]

    scaled_rgb = cv2.resize(premultiplied, (width, height), interpolation=interpolation)
    scaled_alpha = cv2.resize(alpha, (width, height), interpolation=interpolation)
    scaled_alpha = np.clip(scaled_alpha, 0.0, 1.0)

    safe_alpha = np.maximum(scaled_alpha, 1e-6)
    unpremultiplied = scaled_rgb / safe_alpha[..., None]
    unpremultiplied[scaled_alpha <= 0.0] = 0.0

    result = np.empty((height, width, 4), dtype=np.uint8)
    result[..., :3] = np.clip(unpremultiplied, 0, 255).round().astype(np.uint8)
    result[..., 3] = np.clip(scaled_alpha * 255.0, 0, 255).round().astype(np.uint8)
    return result


RESIZE_OPERATION = Operation(
    key="resize", label="Resize / Print Size", params_type=ResizeParams, run=run
)
