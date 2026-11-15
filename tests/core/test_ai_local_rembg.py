"""Local rembg provider: session reuse, CoreML fallback and options."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from stickinator.core.ai import local_rembg
from stickinator.core.ai.config import LocalConfig
from stickinator.core.ops.base import NeverCancelled, OperationCancelled


def _image() -> np.ndarray:
    image = np.zeros((8, 8, 4), dtype=np.uint8)
    image[..., 3] = 255
    return image


class FakeRembg:
    def __init__(self) -> None:
        self.sessions: list[tuple[str, object]] = []
        self.calls: list[dict[str, object]] = []
        self.fail_coreml = False

    def new_session(self, model: str, providers: object = None) -> str:
        self.sessions.append((model, providers))
        if providers is not None and self.fail_coreml:
            raise RuntimeError("CoreML cannot load this graph")
        return f"{model}:{providers}"

    def remove(self, image: Image.Image, **kwargs: object) -> Image.Image:
        self.calls.append(kwargs)
        result = image.copy()
        result.putalpha(0)
        return result


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    local_rembg.clear_session_cache()


def test_returns_rgba_and_passes_alpha_matting(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRembg()
    monkeypatch.setattr(local_rembg, "_load_rembg", lambda: fake)
    config = LocalConfig(
        model="isnet-general-use",
        alpha_matting=True,
        foreground_threshold=200,
        background_threshold=20,
        erode_size=5,
    )

    result = local_rembg.remove_background(_image(), config, NeverCancelled())

    assert result.shape == (8, 8, 4)
    assert result.dtype == np.uint8
    assert (result[..., 3] == 0).all()
    assert fake.sessions == [("isnet-general-use", None)]
    call = fake.calls[0]
    assert call["alpha_matting"] is True
    assert call["alpha_matting_foreground_threshold"] == 200
    assert call["alpha_matting_background_threshold"] == 20
    assert call["alpha_matting_erode_size"] == 5


def test_reuses_the_session(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRembg()
    monkeypatch.setattr(local_rembg, "_load_rembg", lambda: fake)
    config = LocalConfig()

    local_rembg.remove_background(_image(), config, NeverCancelled())
    local_rembg.remove_background(_image(), config, NeverCancelled())

    assert len(fake.sessions) == 1


def test_coreml_falls_back_to_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRembg()
    fake.fail_coreml = True
    monkeypatch.setattr(local_rembg, "_load_rembg", lambda: fake)

    local_rembg.remove_background(_image(), LocalConfig(use_coreml=True), NeverCancelled())

    assert len(fake.sessions) == 2
    assert fake.sessions[0][1] == [
        "CoreMLExecutionProvider",
        "CPUExecutionProvider",
    ]
    assert fake.sessions[1] == ("isnet-general-use", None)


def test_model_directory_sets_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeRembg()
    monkeypatch.setattr(local_rembg, "_load_rembg", lambda: fake)

    local_rembg.remove_background(_image(), LocalConfig(model_dir=str(tmp_path)), NeverCancelled())

    import os

    assert os.environ["U2NET_HOME"] == str(tmp_path)


def test_cancellation_before_the_run_is_honoured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Cancelled:
        cancelled = True

        def raise_if_cancelled(self) -> None:
            raise OperationCancelled

    fake = FakeRembg()
    monkeypatch.setattr(local_rembg, "_load_rembg", lambda: fake)

    with pytest.raises(OperationCancelled):
        local_rembg.remove_background(_image(), LocalConfig(), Cancelled())

    assert fake.sessions == []
