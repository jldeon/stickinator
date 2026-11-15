"""AI operation dispatch: alpha handling, resizing, binarising and routing."""

from __future__ import annotations

import numpy as np
import pytest

from stickinator.core.ai.config import AiContext, HttpConfig, OpenAIConfig
from stickinator.core.ai.provider import ProviderError
from stickinator.core.ops import bg_ai
from stickinator.core.ops.base import NeverCancelled, OperationContext
from stickinator.core.ops.bg_ai import BG_AI, BgAiParams


def _image(alpha: int = 255) -> np.ndarray:
    image = np.zeros((10, 10, 4), dtype=np.uint8)
    image[..., 0] = 200
    image[..., 1] = 30
    image[..., 3] = alpha
    return image


def _mask(alpha: np.ndarray) -> np.ndarray:
    mask = np.zeros((*alpha.shape, 4), dtype=np.uint8)
    mask[..., 3] = alpha
    return mask


def test_uses_provider_alpha_but_keeps_original_colour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alpha = np.full((10, 10), 255, dtype=np.uint8)
    alpha[:, :5] = 0
    monkeypatch.setattr(
        bg_ai.local_rembg,
        "remove_background",
        lambda image, config, cancel: _mask(alpha),
    )

    result = bg_ai.run(
        _image(),
        BgAiParams(provider="local"),
        OperationContext(ai=AiContext()),
        NeverCancelled(),
    )

    assert tuple(result.image[0, 0, :3]) == (200, 30, 0)
    assert result.image[0, 0, 3] == 0
    assert result.image[0, 9, 3] == 255


def test_resizes_the_mask_back_to_the_original_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    small = np.zeros((4, 4), dtype=np.uint8)
    monkeypatch.setattr(
        bg_ai.local_rembg,
        "remove_background",
        lambda image, config, cancel: _mask(small),
    )

    result = bg_ai.run(
        _image(),
        BgAiParams(provider="local"),
        OperationContext(ai=AiContext()),
        NeverCancelled(),
    )

    assert result.image.shape == (10, 10, 4)
    assert (result.image[..., 3] == 0).all()


def test_binarize_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    alpha = np.full((10, 10), 100, dtype=np.uint8)
    monkeypatch.setattr(
        bg_ai.local_rembg,
        "remove_background",
        lambda image, config, cancel: _mask(alpha),
    )
    context = OperationContext(ai=AiContext())

    kept = bg_ai.run(_image(), BgAiParams(binarize=True, threshold=50), context, NeverCancelled())
    dropped = bg_ai.run(
        _image(), BgAiParams(binarize=True, threshold=128), context, NeverCancelled()
    )

    assert (kept.image[..., 3] == 255).all()
    assert (dropped.image[..., 3] == 0).all()


def test_never_raises_alpha_above_the_original(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bg_ai.local_rembg,
        "remove_background",
        lambda image, config, cancel: _mask(np.full((10, 10), 255, dtype=np.uint8)),
    )

    result = bg_ai.run(
        _image(alpha=0),
        BgAiParams(provider="local"),
        OperationContext(ai=AiContext()),
        NeverCancelled(),
    )

    assert (result.image[..., 3] == 0).all()


def test_routes_remote_providers_with_their_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def fake_openai(
        image: np.ndarray,
        config: object,
        key: str,
        timeout: float,
        cancel: object,
    ) -> np.ndarray:
        seen.update(config=config, key=key, timeout=timeout)
        return _mask(np.zeros((10, 10), dtype=np.uint8))

    monkeypatch.setattr(bg_ai.openai_edits, "remove_background", fake_openai)
    context = OperationContext(ai=AiContext(provider="openai", api_key="secret", timeout=42.0))

    bg_ai.run(_image(), BgAiParams(provider="openai"), context, NeverCancelled())

    assert seen["key"] == "secret"
    assert seen["timeout"] == 42.0
    assert isinstance(seen["config"], OpenAIConfig)


def test_routes_http_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_http(
        image: np.ndarray,
        config: object,
        key: str,
        timeout: float,
        cancel: object,
    ) -> np.ndarray:
        return _mask(np.zeros((10, 10), dtype=np.uint8))

    monkeypatch.setattr(bg_ai.generic_post, "remove_background", fake_http)
    ai = AiContext(provider="http", api_key="k")
    context = OperationContext(ai=ai)

    result = bg_ai.run(_image(), BgAiParams(provider="http"), context, NeverCancelled())

    assert result.image.shape == (10, 10, 4)
    assert isinstance(ai.http, HttpConfig)


def test_missing_ai_context_is_reported() -> None:
    with pytest.raises(ProviderError, match="not available"):
        bg_ai.run(_image(), BgAiParams(), OperationContext(ai=None), NeverCancelled())


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        BgAiParams(provider="cloud")


def test_operation_metadata() -> None:
    assert BG_AI.key == "bg_ai"
    assert BG_AI.params_type is BgAiParams
