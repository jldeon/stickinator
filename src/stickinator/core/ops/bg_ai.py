"""AI background removal: dispatch to the configured provider."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from stickinator.core.ai import generic_post, local_rembg, openai_edits
from stickinator.core.ai.config import HTTP, LOCAL, OPENAI, PROVIDERS
from stickinator.core.ai.provider import ProviderError
from stickinator.core.ops.base import (
    CancelToken,
    Operation,
    OperationContext,
    OperationResult,
    Params,
    RGBAImage,
)


@dataclass(frozen=True, slots=True)
class BgAiParams(Params):
    provider: str = LOCAL
    binarize: bool = False
    threshold: int = 128

    def __post_init__(self) -> None:
        if self.provider not in PROVIDERS:
            msg = f"unknown provider: {self.provider}"
            raise ValueError(msg)
        if not 0 <= self.threshold <= 255:
            msg = "threshold must be between 0 and 255"
            raise ValueError(msg)


def run(
    image: RGBAImage,
    params: BgAiParams,
    context: OperationContext,
    cancel: CancelToken,
) -> OperationResult:
    ai = context.ai
    if ai is None:
        msg = "AI settings are not available for this run."
        raise ProviderError(msg)

    provider = params.provider or ai.provider
    if provider == LOCAL:
        result = local_rembg.remove_background(image, ai.local, cancel)
    elif provider == HTTP:
        result = generic_post.remove_background(image, ai.http, ai.api_key, ai.timeout, cancel)
    elif provider == OPENAI:
        result = openai_edits.remove_background(image, ai.openai, ai.api_key, ai.timeout, cancel)
    else:
        msg = f"unknown provider: {provider}"
        raise ProviderError(msg)

    cancel.raise_if_cancelled()
    return OperationResult(_apply_alpha(image, result, params))


def _apply_alpha(
    image: RGBAImage,
    provider_result: RGBAImage,
    params: BgAiParams,
) -> RGBAImage:
    alpha = np.asarray(provider_result[..., 3], dtype=np.uint8)
    if provider_result.shape[:2] != image.shape[:2]:
        alpha = np.asarray(
            cv2.resize(
                alpha,
                (image.shape[1], image.shape[0]),
                interpolation=cv2.INTER_LINEAR,
            ),
            dtype=np.uint8,
        )

    if params.binarize:
        alpha = np.asarray(np.where(alpha >= params.threshold, 255, 0), dtype=np.uint8)

    # Keep the original colour: only the provider's alpha is trusted.
    result = image.copy()
    result[..., 3] = np.minimum(image[..., 3], alpha)
    return result


BG_AI = Operation(
    key="bg_ai",
    label="Remove BG (AI)",
    params_type=BgAiParams,
    run=run,
)
