"""Loading and saving images.

Everything here is pure Pillow/numpy; the UI decides where files come from and
which path to save to.
"""

from __future__ import annotations

import io
import logging
import math
import os
import stat
import tempfile
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

from stickinator.core.settings import DEFAULT_DPI

logger = logging.getLogger(__name__)

RGBAImage = NDArray[np.uint8]

SUPPORTED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
_SCALAR_MODES = frozenset({"I", "I;16", "I;16B", "I;16L", "F"})
_EXIF_X_RESOLUTION = 282
_EXIF_Y_RESOLUTION = 283
_EXIF_RESOLUTION_UNIT = 296
_EXIF_UNIT_CENTIMETRE = 3


class ImageLoadError(Exception):
    """Raised when an input file cannot be decoded."""


class ImageSaveError(Exception):
    """Raised when the output file cannot be written."""


@dataclass(frozen=True, slots=True)
class LoadedImage:
    """Decoded pixels plus the resolution to use for printing."""

    image: RGBAImage
    dpi: tuple[float, float]
    source_path: Path


def normalise_dpi(value: float | Sequence[float]) -> tuple[float, float]:
    """Coerce a scalar or per-axis DPI into a positive ``(x, y)`` pair."""
    if isinstance(value, int | float):
        x = y = float(value)
    else:
        values = [float(item) for item in value]
        if len(values) == 1:
            x = y = values[0]
        elif len(values) >= 2:
            x, y = values[0], values[1]
        else:
            msg = "dpi must be a number or a sequence of one or two numbers"
            raise ValueError(msg)

    if not (math.isfinite(x) and math.isfinite(y)) or x <= 0 or y <= 0:
        msg = "dpi must be positive and finite"
        raise ValueError(msg)
    return (x, y)


def load_image(path: str | Path, *, default_dpi: float = DEFAULT_DPI) -> LoadedImage:
    """Decode ``path`` into RGBA8, honouring EXIF orientation and ICC profiles."""
    source = Path(path)
    try:
        with Image.open(source) as opened:
            if getattr(opened, "n_frames", 1) > 1:
                # Animated WEBP: the document holds a single still frame.
                opened.seek(0)

            image_format = (opened.format or "").upper()
            if image_format not in SUPPORTED_FORMATS:
                msg = f"Unsupported image format: {image_format or 'unknown'}"
                raise ImageLoadError(msg)

            dpi = _read_dpi(opened) or normalise_dpi(default_dpi)
            icc_profile = opened.info.get("icc_profile")
            image = _to_rgba8(opened, icc_profile=icc_profile)
    except ImageLoadError:
        raise
    except (
        OSError,
        UnidentifiedImageError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        msg = f"Could not read {source.name}: {exc}"
        raise ImageLoadError(msg) from exc

    return LoadedImage(image=image, dpi=dpi, source_path=source)


def save_png(
    path: str | Path,
    image: RGBAImage,
    dpi: float | Sequence[float] = DEFAULT_DPI,
) -> None:
    """Write ``image`` as an RGBA PNG, atomically replacing ``path``."""
    destination = Path(path)
    pixels = _validate_rgba(image)
    x_dpi, y_dpi = normalise_dpi(dpi)

    parent = destination.parent
    if not parent.is_dir():
        msg = f"Folder does not exist: {parent}"
        raise ImageSaveError(msg)

    try:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=parent, prefix=f".{destination.name}.", suffix=".png"
        )
        os.close(descriptor)
    except OSError as exc:
        msg = f"Could not create a temporary file next to {destination.name}: {exc}"
        raise ImageSaveError(msg) from exc

    temporary = Path(temporary_name)
    try:
        Image.fromarray(pixels).save(temporary, format="PNG", dpi=(x_dpi, y_dpi))
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        temporary.chmod(_destination_mode(destination))
        temporary.replace(destination)
        _fsync_directory(parent)
    except Exception as exc:
        with suppress(OSError):
            temporary.unlink()
        msg = f"Could not save {destination.name}: {exc}"
        raise ImageSaveError(msg) from exc


def _destination_mode(destination: Path) -> int:
    try:
        return stat.S_IMODE(destination.stat().st_mode)
    except OSError:
        return 0o644


def _fsync_directory(directory: Path) -> None:
    """Best-effort directory sync; some filesystems refuse fsync on a directory."""
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _validate_rgba(image: RGBAImage) -> RGBAImage:
    array = np.asarray(image)
    if array.dtype != np.uint8 or array.ndim != 3 or array.shape[2] != 4:
        msg = "image must be an (H, W, 4) uint8 array"
        raise ValueError(msg)
    return cast("RGBAImage", np.ascontiguousarray(array))


def _to_rgba8(image: Image.Image, *, icc_profile: Any) -> RGBAImage:
    # Orientation is spatial and colour management is not; either order works,
    # but transposing first keeps the ICC crop dimensions consistent.
    transposed = ImageOps.exif_transpose(image)
    if transposed.mode in _SCALAR_MODES:
        # 16-bit and float greyscale rarely carry a profile, and ImageCms would
        # clip them to 8 bits before scaling.
        return _scalar_to_rgba8(transposed)
    colour_managed = _apply_icc_profile(transposed, icc_profile)
    return _finalise(np.asarray(colour_managed.convert("RGBA")))


def _apply_icc_profile(image: Image.Image, icc_profile: Any) -> Image.Image:
    if not icc_profile or image.mode in _SCALAR_MODES:
        return image

    # A palette image carries transparency in info, which convert("RGB") drops.
    if image.mode == "P" and "transparency" in image.info:
        image = image.convert("RGBA")

    try:
        source_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
        srgb_profile = ImageCms.createProfile("sRGB")
        has_alpha = "A" in image.getbands()
        alpha = image.getchannel("A") if has_alpha else None
        # CMYK and LAB profiles only accept their own mode as input.
        base = image if image.mode in {"CMYK", "LAB"} else image.convert("RGB")
        converted = ImageCms.profileToProfile(base, source_profile, srgb_profile, outputMode="RGB")
    except (ImageCms.PyCMSError, OSError, ValueError) as exc:
        logger.warning("Ignoring unreadable ICC profile: %s", exc)
        return image

    if converted is None:
        return image
    if alpha is not None:
        converted.putalpha(alpha)
    return converted


def _scalar_to_rgba8(image: Image.Image) -> RGBAImage:
    """Expand 16-bit and float greyscale data instead of clipping it."""
    values = np.asarray(image)
    if values.size == 0:
        grey = np.zeros(values.shape, dtype=np.uint8)
    else:
        numeric = values.astype(np.float64)
        peak = float(np.nanmax(numeric))
        if np.issubdtype(values.dtype, np.floating):
            scale = 255.0 if peak <= 1.0 else (255.0 / peak if peak > 0 else 0.0)
        elif peak <= 255.0:
            scale = 1.0
        elif peak <= 65535.0:
            scale = 1.0 / 257.0
        else:
            scale = 255.0 / peak if peak > 0 else 0.0
        grey = np.clip(numeric * scale, 0.0, 255.0).round().astype(np.uint8)

    alpha = np.full(grey.shape, 255, dtype=np.uint8)
    return _finalise(np.stack((grey, grey, grey, alpha), axis=-1))


def _finalise(array: NDArray[Any]) -> RGBAImage:
    rgba = np.ascontiguousarray(array, dtype=np.uint8)
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        msg = "Decoded image is not RGBA"
        raise ImageLoadError(msg)
    return rgba


def _read_dpi(image: Image.Image) -> tuple[float, float] | None:
    dpi = _coerce_dpi(image.info.get("dpi"))
    if dpi is not None:
        return dpi

    try:
        exif = image.getexif()
    except (AttributeError, OSError, ValueError):
        return None
    if not exif:
        return None

    x_resolution = exif.get(_EXIF_X_RESOLUTION)
    y_resolution = exif.get(_EXIF_Y_RESOLUTION)
    if x_resolution is None or y_resolution is None:
        return None
    try:
        x = float(x_resolution)
        y = float(y_resolution)
    except (TypeError, ValueError, ZeroDivisionError):
        return None

    if exif.get(_EXIF_RESOLUTION_UNIT) == _EXIF_UNIT_CENTIMETRE:
        x *= 2.54
        y *= 2.54
    if x <= 0 or y <= 0:
        return None
    return (x, y)


def _coerce_dpi(value: Any) -> tuple[float, float] | None:
    if value is None:
        return None
    try:
        return normalise_dpi(value)
    except (TypeError, ValueError):
        return None
