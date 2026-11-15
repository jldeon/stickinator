"""OpenAI-compatible ``/v1/images/edits`` provider."""

from __future__ import annotations

import base64

import httpx
import numpy as np

from stickinator.core.ai import http_utils
from stickinator.core.ai.config import OpenAIConfig
from stickinator.core.ai.provider import ProviderError
from stickinator.core.ops.base import CancelToken, RGBAImage

TRANSPARENCY_FIELDS = ("background", "output_format")


def remove_background(
    image: RGBAImage,
    config: OpenAIConfig,
    api_key: str,
    timeout: float,
    cancel: CancelToken,
) -> RGBAImage:
    if not api_key:
        msg = "No API key is configured for the OpenAI provider."
        raise ProviderError(msg)

    endpoint = f"{config.base_url.rstrip('/')}/images/edits"
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "model": config.model,
        "prompt": config.prompt,
        "background": "transparent",
        "output_format": "png",
    }
    files = {"image": ("image.png", http_utils.png_bytes(image), "image/png")}

    cancel.raise_if_cancelled()
    try:
        with http_utils.make_client(timeout) as client:
            response = client.post(endpoint, headers=headers, files=files, data=data)
            if response.status_code in {400, 422} and _rejects_transparency(response):
                # Older compatible servers do not know the transparency fields.
                for field in TRANSPARENCY_FIELDS:
                    data.pop(field, None)
                response = client.post(endpoint, headers=headers, files=files, data=data)

            if response.status_code >= 400:
                msg = (
                    f"The image service returned HTTP {response.status_code}: {response.text[:200]}"
                )
                raise ProviderError(msg)

            result = _decode_result(client, response, cancel)
    except httpx.HTTPError as exc:
        msg = f"Could not reach the image service: {exc}"
        raise ProviderError(msg) from exc

    cancel.raise_if_cancelled()
    if np.all(result[..., 3] == 255):
        msg = (
            "The image service returned an opaque image; it may not support "
            "transparent backgrounds."
        )
        raise ProviderError(msg)
    return result


def _rejects_transparency(response: httpx.Response) -> bool:
    body = response.text.lower()
    return any(field in body for field in TRANSPARENCY_FIELDS)


def _decode_result(
    client: httpx.Client,
    response: httpx.Response,
    cancel: CancelToken,
) -> RGBAImage:
    try:
        payload = response.json()
    except ValueError as exc:
        msg = "The image service returned an unreadable response."
        raise ProviderError(msg) from exc

    entries = payload.get("data") if isinstance(payload, dict) else None
    if not entries:
        msg = "The image service returned no image."
        raise ProviderError(msg)

    entry = entries[0]
    if isinstance(entry, dict) and entry.get("b64_json"):
        raw = base64.b64decode(entry["b64_json"])
        return http_utils.decode_image(raw)

    if isinstance(entry, dict) and entry.get("url"):
        cancel.raise_if_cancelled()
        download = client.get(entry["url"])
        if download.status_code >= 400:
            msg = f"Could not download the edited image (HTTP {download.status_code})."
            raise ProviderError(msg)
        return http_utils.decode_image(download.content)

    msg = "The image service response contained neither b64_json nor a url."
    raise ProviderError(msg)
