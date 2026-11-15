"""Shared HTTP helpers for remote providers."""

from __future__ import annotations

import io

import httpx
import numpy as np
from PIL import Image

from stickinator.core.ai.provider import ProviderError
from stickinator.core.ops.base import RGBAImage


def make_client(timeout: float) -> httpx.Client:
    """Indirection so tests can inject an ``httpx.MockTransport``."""
    return httpx.Client(timeout=timeout)


def png_bytes(image: RGBAImage) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(image).save(buffer, format="PNG")
    return buffer.getvalue()


def decode_image(data: bytes) -> RGBAImage:
    try:
        with Image.open(io.BytesIO(data)) as opened:
            converted = opened.convert("RGBA")
    except (OSError, ValueError) as exc:
        msg = f"The service did not return a usable image: {exc}"
        raise ProviderError(msg) from exc
    return np.asarray(converted, dtype=np.uint8)


def parse_lines(text: str) -> dict[str, str]:
    """Parse ``Name: value`` lines, ignoring blanks and comments."""
    parsed: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition(":")
        if not separator:
            msg = f"Expected 'Name: value' in: {line}"
            raise ProviderError(msg)
        parsed[name.strip()] = value.strip()
    return parsed
