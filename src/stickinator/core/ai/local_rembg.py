"""Local background removal through rembg. Offline once the model is cached."""

from __future__ import annotations

import os
from typing import Any

import numpy as np
from PIL import Image

from stickinator.core.ai.config import LocalConfig
from stickinator.core.ai.provider import ProviderError
from stickinator.core.ops.base import CancelToken, RGBAImage

MODELS = ("u2net", "isnet-general-use", "birefnet-general")
_SESSIONS: dict[tuple[str, bool, str], Any] = {}


def _load_rembg() -> Any:
    """Indirection so tests can run without onnxruntime or model downloads."""
    import rembg

    return rembg


def remove_background(
    image: RGBAImage,
    config: LocalConfig,
    cancel: CancelToken,
) -> RGBAImage:
    cancel.raise_if_cancelled()
    rembg = _load_rembg()
    if config.model_dir:
        os.environ["U2NET_HOME"] = config.model_dir

    session = _session(rembg, config)
    cancel.raise_if_cancelled()

    try:
        result = rembg.remove(
            Image.fromarray(image),
            session=session,
            alpha_matting=config.alpha_matting,
            alpha_matting_foreground_threshold=config.foreground_threshold,
            alpha_matting_background_threshold=config.background_threshold,
            alpha_matting_erode_size=config.erode_size,
        )
    except Exception as exc:
        msg = f"Local background removal failed: {exc}"
        raise ProviderError(msg) from exc

    cancel.raise_if_cancelled()
    return np.asarray(result.convert("RGBA"))


def _session(rembg: Any, config: LocalConfig) -> Any:
    key = (config.model, config.use_coreml, config.model_dir)
    if key in _SESSIONS:
        return _SESSIONS[key]

    providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"] if config.use_coreml else None
    try:
        session = (
            rembg.new_session(config.model, providers=providers)
            if providers
            else rembg.new_session(config.model)
        )
    except Exception:
        if providers is None:
            raise
        # CoreML can fail to load the graph; fall back instead of failing the run.
        session = rembg.new_session(config.model)

    _SESSIONS[key] = session
    return session


def clear_session_cache() -> None:
    _SESSIONS.clear()
