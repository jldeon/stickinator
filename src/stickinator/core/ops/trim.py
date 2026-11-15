"""Crop away transparent padding around the content."""

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


@dataclass(frozen=True, slots=True)
class TrimParams(Params):
    threshold: int = 128
    margin: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.threshold <= 255:
            msg = "threshold must be between 0 and 255"
            raise ValueError(msg)
        if self.margin < 0:
            msg = "margin must not be negative"
            raise ValueError(msg)


def run(
    image: RGBAImage,
    params: TrimParams,
    context: OperationContext,
    cancel: CancelToken,
) -> OperationResult:
    cancel.raise_if_cancelled()
    height, width = image.shape[:2]
    opaque = image[..., 3] >= params.threshold
    rows = np.flatnonzero(opaque.any(axis=1))
    columns = np.flatnonzero(opaque.any(axis=0))

    if rows.size == 0 or columns.size == 0:
        msg = "The image is completely transparent; nothing to trim."
        raise ValueError(msg)

    top = max(int(rows[0]) - params.margin, 0)
    bottom = min(int(rows[-1]) + 1 + params.margin, height)
    left = max(int(columns[0]) - params.margin, 0)
    right = min(int(columns[-1]) + 1 + params.margin, width)

    return OperationResult(image[top:bottom, left:right].copy())


TRIM = Operation(key="trim", label="Trim", params_type=TrimParams, run=run)
