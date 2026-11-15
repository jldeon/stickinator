"""Remote providers against httpx.MockTransport, including OpenAI fallbacks."""

from __future__ import annotations

import base64
import io
import json
from collections.abc import Callable

import httpx
import numpy as np
import pytest
from PIL import Image

from stickinator.core.ai import generic_post, http_utils, openai_edits
from stickinator.core.ai.config import HttpConfig, OpenAIConfig
from stickinator.core.ai.provider import ProviderError
from stickinator.core.ops.base import NeverCancelled


def _image() -> np.ndarray:
    image = np.zeros((10, 10, 4), dtype=np.uint8)
    image[..., 0] = 200
    image[..., 3] = 255
    return image


def _png_bytes(alpha: int = 0) -> bytes:
    image = Image.new("RGBA", (10, 10), (10, 20, 30, alpha))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _client_factory(
    handler: Callable[[httpx.Request], httpx.Response],
) -> Callable[[float], httpx.Client]:
    def make_client(timeout: float) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler), timeout=timeout)

    return make_client


def test_generic_post_sends_the_image_and_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=_png_bytes(alpha=0))

    monkeypatch.setattr(http_utils, "make_client", _client_factory(handler))
    config = HttpConfig(
        url="https://remove.example/api",
        field_name="file",
        auth_header="Authorization",
        auth_format="Bearer {key}",
        extra_headers="X-Trace: abc",
        extra_fields="size: auto",
    )

    result = generic_post.remove_background(_image(), config, "secret", 12.0, NeverCancelled())

    request = seen[0]
    assert request.url == "https://remove.example/api"
    assert request.headers["Authorization"] == "Bearer secret"
    assert request.headers["X-Trace"] == "abc"
    body = request.read()
    assert b'name="file"' in body
    assert b"size" in body
    assert result.shape == (10, 10, 4)


def test_generic_post_reports_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad key")

    monkeypatch.setattr(http_utils, "make_client", _client_factory(handler))

    with pytest.raises(ProviderError, match="HTTP 401"):
        generic_post.remove_background(
            _image(), HttpConfig(url="https://x"), "", 5.0, NeverCancelled()
        )


def test_generic_post_requires_a_url() -> None:
    with pytest.raises(ProviderError, match="No endpoint URL"):
        generic_post.remove_background(_image(), HttpConfig(), "", 5.0, NeverCancelled())


def test_openai_sends_transparency_fields_and_decodes_b64(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encoded = base64.b64encode(_png_bytes(alpha=0)).decode("ascii")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": [{"b64_json": encoded}]})

    monkeypatch.setattr(http_utils, "make_client", _client_factory(handler))

    result = openai_edits.remove_background(_image(), OpenAIConfig(), "key", 20.0, NeverCancelled())

    body = seen[0].read()
    assert b"background" in body
    assert b"output_format" in body
    assert seen[0].url.path.endswith("/images/edits")
    assert (result[..., 3] == 0).all()


def test_openai_downloads_a_url_result(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.method == "POST":
            return httpx.Response(200, json={"data": [{"url": "https://cdn.example/edit.png"}]})
        return httpx.Response(200, content=_png_bytes(alpha=0))

    monkeypatch.setattr(http_utils, "make_client", _client_factory(handler))

    result = openai_edits.remove_background(_image(), OpenAIConfig(), "key", 20.0, NeverCancelled())

    assert calls[-1] == "https://cdn.example/edit.png"
    assert result.shape == (10, 10, 4)


def test_openai_retries_without_transparency_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encoded = base64.b64encode(_png_bytes(alpha=0)).decode("ascii")
    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        bodies.append(body)
        if len(bodies) == 1:
            return httpx.Response(400, text="unknown parameter: background")
        return httpx.Response(200, json={"data": [{"b64_json": encoded}]})

    monkeypatch.setattr(http_utils, "make_client", _client_factory(handler))

    openai_edits.remove_background(_image(), OpenAIConfig(), "key", 20.0, NeverCancelled())

    assert b'name="background"' in bodies[0]
    assert b'name="background"' not in bodies[1]


def test_openai_rejects_an_opaque_result(monkeypatch: pytest.MonkeyPatch) -> None:
    encoded = base64.b64encode(_png_bytes(alpha=255)).decode("ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"b64_json": encoded}]})

    monkeypatch.setattr(http_utils, "make_client", _client_factory(handler))

    with pytest.raises(ProviderError, match="opaque"):
        openai_edits.remove_background(_image(), OpenAIConfig(), "key", 20.0, NeverCancelled())


def test_openai_requires_an_api_key() -> None:
    with pytest.raises(ProviderError, match="No API key"):
        openai_edits.remove_background(_image(), OpenAIConfig(), "", 20.0, NeverCancelled())


def test_parse_lines_rejects_malformed_input() -> None:
    with pytest.raises(ProviderError, match="Name: value"):
        http_utils.parse_lines("this line has no colon")


def test_decode_image_reports_garbage() -> None:
    with pytest.raises(ProviderError, match="usable image"):
        http_utils.decode_image(json.dumps({"not": "an image"}).encode())
