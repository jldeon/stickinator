"""Loading behaviour: orientation, colour management, DPI and mode conversion."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageCms, features

from stickinator.core.io import ImageLoadError, load_image


def test_loads_png_and_reads_dpi(tmp_path: Path) -> None:
    source = tmp_path / "input.png"
    Image.new("RGBA", (32, 16), (10, 20, 30, 128)).save(source, dpi=(150, 150))

    loaded = load_image(source)

    assert loaded.image.shape == (16, 32, 4)
    assert loaded.image.dtype == np.uint8
    assert loaded.dpi == pytest.approx((150.0, 150.0), abs=0.5)
    assert loaded.source_path == source
    assert tuple(loaded.image[0, 0]) == (10, 20, 30, 128)


def test_missing_dpi_uses_default(tmp_path: Path) -> None:
    source = tmp_path / "input.png"
    Image.new("RGB", (4, 4), (1, 2, 3)).save(source)

    loaded = load_image(source, default_dpi=72)

    assert loaded.dpi == (72.0, 72.0)


def test_exif_orientation_is_applied(tmp_path: Path) -> None:
    source = tmp_path / "rotated.jpg"
    image = Image.new("RGB", (40, 20), (255, 0, 0))
    image.paste(Image.new("RGB", (20, 20), (0, 0, 255)), (20, 0))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees clockwise when displaying
    image.save(source, exif=exif.tobytes(), quality=95)

    loaded = load_image(source)

    assert loaded.image.shape == (40, 20, 4)
    # The original left (red) half becomes the top after a clockwise rotation.
    top = loaded.image[:10, :, :3].reshape(-1, 3).mean(axis=0)
    bottom = loaded.image[-10:, :, :3].reshape(-1, 3).mean(axis=0)
    assert top[0] > 200 and top[2] < 60
    assert bottom[2] > 200 and bottom[0] < 60


def test_cmyk_jpeg_becomes_opaque_rgba(tmp_path: Path) -> None:
    source = tmp_path / "cmyk.jpg"
    Image.new("CMYK", (24, 12), (0, 128, 255, 0)).save(source, quality=95)

    loaded = load_image(source)

    assert loaded.image.shape == (12, 24, 4)
    assert (loaded.image[..., 3] == 255).all()
    assert loaded.image[..., 0].mean() > 200
    assert loaded.image[..., 2].mean() < 60


def test_16bit_greyscale_is_scaled_not_clipped(tmp_path: Path) -> None:
    source = tmp_path / "deep.png"
    values = np.array([[0, 257], [514, 65535]], dtype=np.uint16)
    image = Image.fromarray(values)
    assert image.mode.startswith("I;16")
    image.save(source)

    loaded = load_image(source)

    assert loaded.image[0, 0, 0] == 0
    assert loaded.image[0, 1, 0] == 1
    assert loaded.image[1, 0, 0] == 2
    assert loaded.image[1, 1, 0] == 255


def test_palette_transparency_becomes_alpha(tmp_path: Path) -> None:
    source = tmp_path / "palette.png"
    image = Image.new("P", (8, 8))
    image.putpalette([255, 0, 0, 0, 255, 0, *([0] * 759)])
    image.save(source, transparency=0)

    loaded = load_image(source)

    assert (loaded.image[..., 3] == 0).all()


@pytest.mark.skipif(not features.check("webp"), reason="Pillow built without WEBP")
def test_animated_webp_uses_first_frame(tmp_path: Path) -> None:
    source = tmp_path / "animated.webp"
    first = Image.new("RGB", (16, 16), (255, 0, 0))
    second = Image.new("RGB", (16, 16), (0, 0, 255))
    first.save(source, save_all=True, append_images=[second], duration=100, loop=0)

    loaded = load_image(source)

    assert loaded.image.shape == (16, 16, 4)
    assert loaded.image[..., 0].mean() > 200
    assert loaded.image[..., 2].mean() < 60


def test_unsupported_format_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "picture.bmp"
    Image.new("RGB", (4, 4), (1, 2, 3)).save(source)

    with pytest.raises(ImageLoadError, match="Unsupported image format"):
        load_image(source)


def test_unreadable_file_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "broken.png"
    source.write_text("this is not an image")

    with pytest.raises(ImageLoadError):
        load_image(source)


def test_corrupt_icc_profile_is_ignored(tmp_path: Path) -> None:
    source = tmp_path / "bad-profile.png"
    Image.new("RGB", (8, 8), (1, 2, 3)).save(source, icc_profile=b"not an ICC profile")

    loaded = load_image(source)

    assert tuple(loaded.image[0, 0, :3]) == (1, 2, 3)


def test_srgb_profile_is_applied_without_shifting_colour(tmp_path: Path) -> None:
    source = tmp_path / "srgb.png"
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(source, icc_profile=profile)

    loaded = load_image(source)

    assert loaded.image[0, 0, :3] == pytest.approx((10, 20, 30), abs=2)


def test_palette_transparency_survives_an_icc_profile(tmp_path: Path) -> None:
    source = tmp_path / "palette-profile.png"
    image = Image.new("P", (8, 8))
    image.putpalette([255, 0, 0, *([0] * 765)])
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    image.save(source, transparency=0, icc_profile=profile)

    loaded = load_image(source)

    assert (loaded.image[..., 3] == 0).all()


def test_exif_resolution_is_used_when_there_is_no_phys_chunk(tmp_path: Path) -> None:
    source = tmp_path / "exif-dpi.png"
    exif = Image.Exif()
    exif[0x011A] = 300  # XResolution
    exif[0x011B] = 300  # YResolution
    exif[0x0128] = 2  # inches
    Image.new("RGB", (8, 8), (5, 6, 7)).save(source, exif=exif)

    loaded = load_image(source)

    assert loaded.dpi == pytest.approx((300.0, 300.0), abs=0.5)
