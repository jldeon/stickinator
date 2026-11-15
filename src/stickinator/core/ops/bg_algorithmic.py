"""Algorithmic background removal: colour keying and GrabCut."""

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

COLOR_KEY = "color_key"
GRABCUT = "grabcut"
AUTO = "auto"
PICKED = "picked"
CONTIGUOUS = "contiguous"
GLOBAL = "global"
INSET_UNITS = frozenset({"percent", "px"})


@dataclass(frozen=True, slots=True)
class BgRemovalParams(Params):
    method: str = COLOR_KEY
    color_source: str = AUTO
    color: tuple[int, int, int] = (255, 255, 255)
    tolerance: float = 10.0
    mode: str = CONTIGUOUS
    seed_x: int = -1
    seed_y: int = -1
    feather: float = 0.0
    despeckle: int = 0
    inset: float = 5.0
    inset_unit: str = "percent"
    iterations: int = 5

    def __post_init__(self) -> None:
        if self.method not in {COLOR_KEY, GRABCUT}:
            msg = f"unknown method: {self.method}"
            raise ValueError(msg)
        if self.color_source not in {AUTO, PICKED}:
            msg = f"unknown colour source: {self.color_source}"
            raise ValueError(msg)
        if self.mode not in {CONTIGUOUS, GLOBAL}:
            msg = f"unknown mode: {self.mode}"
            raise ValueError(msg)
        if self.inset_unit not in INSET_UNITS:
            msg = f"unknown inset unit: {self.inset_unit}"
            raise ValueError(msg)
        if self.tolerance < 0:
            msg = "tolerance must not be negative"
            raise ValueError(msg)
        if self.feather < 0:
            msg = "feather must not be negative"
            raise ValueError(msg)
        if self.despeckle < 0:
            msg = "despeckle must not be negative"
            raise ValueError(msg)
        if self.iterations < 1:
            msg = "iterations must be at least 1"
            raise ValueError(msg)
        if self.inset < 0:
            msg = "inset must not be negative"
            raise ValueError(msg)
        if len(self.color) != 3 or any(not 0 <= channel <= 255 for channel in self.color):
            msg = "color must be three channels between 0 and 255"
            raise ValueError(msg)


def run(
    image: RGBAImage,
    params: BgRemovalParams,
    context: OperationContext,
    cancel: CancelToken,
) -> OperationResult:
    cancel.raise_if_cancelled()
    if params.method == GRABCUT:
        alpha = _grabcut_alpha(image, params, cancel)
    else:
        alpha = _color_key_alpha(image, params, cancel)

    result = image.copy()
    result[..., 3] = np.minimum(image[..., 3], alpha)
    return OperationResult(result)


def _color_key_alpha(
    image: RGBAImage,
    params: BgRemovalParams,
    cancel: CancelToken,
) -> np.ndarray:
    lab = cv2.cvtColor(image[..., :3].astype(np.float32) / 255.0, cv2.COLOR_RGB2Lab)
    background = params.color if params.color_source == PICKED else dominant_edge_colour(image)
    background_lab = cv2.cvtColor(
        np.array([[background]], dtype=np.float32) / 255.0, cv2.COLOR_RGB2Lab
    )[0, 0]

    distance = np.linalg.norm(lab - background_lab, axis=2)
    candidate = distance <= params.tolerance
    cancel.raise_if_cancelled()

    if params.mode == CONTIGUOUS:
        candidate = _connected_to_seed(candidate, params)

    removed = candidate.astype(np.float32)
    if params.feather > 0:
        sigma = max(0.5, params.feather / 2.0)
        removed = cv2.GaussianBlur(removed, (0, 0), sigma)
    cancel.raise_if_cancelled()

    alpha = (
        (image[..., 3].astype(np.float32) * (1.0 - removed)).round().clip(0, 255).astype(np.uint8)
    )

    if params.despeckle > 0:
        alpha = _despeckle(alpha, params.despeckle)
    return alpha


def dominant_edge_colour(image: RGBAImage) -> tuple[int, int, int]:
    """Most common opaque colour along the 1 px border."""
    rgb = image[..., :3]
    alpha = image[..., 3]
    border_rgb = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]], axis=0)
    border_alpha = np.concatenate([alpha[0], alpha[-1], alpha[:, 0], alpha[:, -1]], axis=0)
    visible = border_rgb[border_alpha > 0]
    if visible.size == 0:
        return (255, 255, 255)

    packed = (
        (visible[:, 0].astype(np.uint32) << 16)
        | (visible[:, 1].astype(np.uint32) << 8)
        | visible[:, 2].astype(np.uint32)
    )
    values, counts = np.unique(packed, return_counts=True)
    best = int(values[int(np.argmax(counts))])
    return ((best >> 16) & 0xFF, (best >> 8) & 0xFF, best & 0xFF)


def _connected_to_seed(candidate: np.ndarray, params: BgRemovalParams) -> np.ndarray:
    count, labels = cv2.connectedComponents(candidate.astype(np.uint8), connectivity=8)
    if count <= 1:
        return np.zeros_like(candidate)

    keep = np.zeros(count, dtype=bool)
    keep[labels[0, :]] = True
    keep[labels[-1, :]] = True
    keep[labels[:, 0]] = True
    keep[labels[:, -1]] = True
    keep[0] = False

    has_seed = params.seed_x >= 0 and params.seed_y >= 0
    if has_seed:
        if not (0 <= params.seed_x < candidate.shape[1]) or not (
            0 <= params.seed_y < candidate.shape[0]
        ):
            msg = "The picked point is outside the image."
            raise ValueError(msg)
        if not candidate[params.seed_y, params.seed_x]:
            msg = (
                "The picked point does not match the background colour. "
                "Increase the tolerance or pick another point."
            )
            raise ValueError(msg)
        keep[labels[params.seed_y, params.seed_x]] = True

    selected = keep[labels]
    if not selected.any():
        msg = (
            "The background does not touch the image edge. "
            "Pick a point in the background or switch to Global mode."
        )
        raise ValueError(msg)
    return selected


def _despeckle(alpha: np.ndarray, minimum: int) -> np.ndarray:
    count, labels = cv2.connectedComponents((alpha > 0).astype(np.uint8), connectivity=8)
    if count <= 1:
        return alpha

    sizes = np.bincount(labels.ravel().astype(np.intp), minlength=count)
    small = sizes < minimum
    small[0] = False
    cleaned = alpha.copy()
    cleaned[small[labels]] = 0
    return cleaned


def _grabcut_alpha(
    image: RGBAImage,
    params: BgRemovalParams,
    cancel: CancelToken,
) -> np.ndarray:
    height, width = image.shape[:2]
    if params.inset_unit == "px":
        inset_x = inset_y = round(params.inset)
    else:
        inset_x = round(width * params.inset / 100.0)
        inset_y = round(height * params.inset / 100.0)

    inset_x = min(inset_x, max(0, (width - 2) // 2))
    inset_y = min(inset_y, max(0, (height - 2) // 2))
    rectangle = (
        inset_x,
        inset_y,
        max(1, width - 2 * inset_x),
        max(1, height - 2 * inset_y),
    )

    bgr = cv2.cvtColor(image[..., :3], cv2.COLOR_RGB2BGR)
    mask = np.zeros((height, width), np.uint8)
    background_model = np.zeros((1, 65), np.float64)
    foreground_model = np.zeros((1, 65), np.float64)

    cancel.raise_if_cancelled()
    cv2.grabCut(
        bgr,
        mask,
        rectangle,
        background_model,
        foreground_model,
        params.iterations,
        cv2.GC_INIT_WITH_RECT,
    )
    cancel.raise_if_cancelled()

    foreground = (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)
    return np.where(foreground, image[..., 3], 0).astype(np.uint8)


BG_REMOVAL = Operation(
    key="bg_algorithmic",
    label="Remove BG",
    params_type=BgRemovalParams,
    run=run,
)
