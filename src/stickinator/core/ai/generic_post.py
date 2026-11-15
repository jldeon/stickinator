"""Generic multipart POST provider (remove.bg, rembg-server and friends)."""

from __future__ import annotations

import httpx

from stickinator.core.ai import http_utils
from stickinator.core.ai.config import HttpConfig
from stickinator.core.ai.provider import ProviderError
from stickinator.core.ops.base import CancelToken, RGBAImage


def remove_background(
    image: RGBAImage,
    config: HttpConfig,
    api_key: str,
    timeout: float,
    cancel: CancelToken,
) -> RGBAImage:
    if not config.url:
        msg = "No endpoint URL is configured for the generic HTTP provider."
        raise ProviderError(msg)

    headers = http_utils.parse_lines(config.extra_headers)
    if config.auth_header and api_key:
        headers[config.auth_header] = config.auth_format.format(key=api_key)

    data = http_utils.parse_lines(config.extra_fields)
    files = {config.field_name: ("image.png", http_utils.png_bytes(image), "image/png")}

    cancel.raise_if_cancelled()
    try:
        with http_utils.make_client(timeout) as client:
            response = client.post(config.url, headers=headers, data=data, files=files)
    except httpx.HTTPError as exc:
        msg = f"Could not reach the background service: {exc}"
        raise ProviderError(msg) from exc
    cancel.raise_if_cancelled()

    if response.status_code >= 400:
        msg = f"The background service returned HTTP {response.status_code}: {response.text[:200]}"
        raise ProviderError(msg)

    return http_utils.decode_image(response.content)
