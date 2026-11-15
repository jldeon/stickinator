"""Saving behaviour: PNG output, DPI metadata and atomic replacement."""

from __future__ import annotations

import stat
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from stickinator.core.io import ImageSaveError, load_image, save_png


def _solid(value: int, size: tuple[int, int] = (4, 4)) -> np.ndarray:
    image = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    image[..., 0] = value
    image[..., 3] = 255
    return image


def test_saves_rgba_png_with_dpi(tmp_path: Path) -> None:
    destination = tmp_path / "out.png"
    image = _solid(9)

    save_png(destination, image, (300, 300))

    with Image.open(destination) as saved:
        assert saved.mode == "RGBA"
        assert saved.info["dpi"][0] == pytest.approx(300, abs=0.5)
    assert np.array_equal(load_image(destination).image, image)


def test_dpi_accepts_a_scalar(tmp_path: Path) -> None:
    destination = tmp_path / "out.png"

    save_png(destination, _solid(0), 72)

    assert load_image(destination).dpi == pytest.approx((72.0, 72.0), abs=0.5)


def test_rejects_non_rgba_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"\(H, W, 4\)"):
        save_png(tmp_path / "out.png", np.zeros((4, 4, 3), dtype=np.uint8), 300)


def test_rejects_missing_folder(tmp_path: Path) -> None:
    with pytest.raises(ImageSaveError, match="Folder does not exist"):
        save_png(tmp_path / "missing" / "out.png", _solid(0), 300)


def test_failed_save_leaves_the_existing_file_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "out.png"
    save_png(destination, _solid(10), 300)
    before = destination.read_bytes()

    def explode(self: Image.Image, fp: object, *args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(Image.Image, "save", explode)

    with pytest.raises(ImageSaveError, match="disk full"):
        save_png(destination, _solid(200), 300)

    assert destination.read_bytes() == before
    assert [entry.name for entry in tmp_path.iterdir()] == [destination.name]


def test_preserves_the_existing_file_permissions(tmp_path: Path) -> None:
    destination = tmp_path / "out.png"
    save_png(destination, _solid(10), 300)
    destination.chmod(0o600)

    save_png(destination, _solid(20), 300)

    assert stat.S_IMODE(destination.stat().st_mode) == 0o600


def test_saves_read_only_pixels(tmp_path: Path) -> None:
    image = _solid(11)
    image.setflags(write=False)
    destination = tmp_path / "out.png"

    save_png(destination, image, 300)

    assert np.array_equal(load_image(destination).image, _solid(11))
