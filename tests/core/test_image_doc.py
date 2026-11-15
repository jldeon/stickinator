"""Document behaviour: history bounds, dirty state and immutability."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from stickinator.core.image_doc import Document
from stickinator.core.io import save_png
from stickinator.core.settings import Settings


def _image(value: int, size: tuple[int, int] = (8, 8)) -> np.ndarray:
    image = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    image[..., 0] = value
    image[..., 3] = 255
    return image


def test_apply_then_undo_restores_pixels_and_dpi() -> None:
    document = Document(_image(10), (300, 300))

    document.apply(_image(20), dpi=(150, 150))

    assert document.dpi == (150.0, 150.0)
    assert document.dirty
    assert document.can_undo
    assert document.undo()
    assert np.array_equal(document.image, _image(10))
    assert document.dpi == (300.0, 300.0)
    assert not document.dirty


def test_undo_with_empty_history_returns_false() -> None:
    document = Document(_image(0))

    assert not document.can_undo
    assert not document.undo()


def test_mark_saved_clears_dirty_and_undo_makes_it_dirty_again(tmp_path: Path) -> None:
    document = Document(_image(0))
    document.apply(_image(1))
    output = tmp_path / "out.png"

    document.mark_saved(output)

    assert not document.dirty
    assert document.source_path == output
    assert document.undo()
    assert document.dirty


def test_undo_back_to_the_saved_state_is_clean(tmp_path: Path) -> None:
    document = Document(_image(0))
    document.apply(_image(1))
    document.mark_saved(tmp_path / "out.png")
    document.apply(_image(2))

    assert document.dirty

    assert document.undo()
    assert not document.dirty


def test_set_dpi_is_undoable() -> None:
    document = Document(_image(0), 300)

    document.set_dpi(600)

    assert document.dpi == (600.0, 600.0)
    assert document.undo()
    assert document.dpi == (300.0, 300.0)
    assert np.array_equal(document.image, _image(0))


def test_history_drops_the_oldest_entry_when_over_the_limit() -> None:
    document = Document(_image(0), undo_memory_limit_bytes=512)

    for value in range(1, 4):
        document.apply(_image(value))

    assert document.undo_depth == 2
    assert document.undo_memory_bytes == 512

    assert document.undo()
    assert np.array_equal(document.image, _image(2))
    assert document.undo()
    assert np.array_equal(document.image, _image(1))
    assert not document.can_undo


def test_single_snapshot_is_kept_when_the_limit_is_tiny() -> None:
    document = Document(_image(0), undo_memory_limit_bytes=1)

    document.apply(_image(1))

    assert document.undo_depth == 1


def test_zero_limit_disables_history() -> None:
    document = Document(_image(0), undo_memory_limit_bytes=0)

    document.apply(_image(1))

    assert document.undo_depth == 0
    assert not document.can_undo


def test_lowering_the_limit_trims_history() -> None:
    document = Document(_image(0), undo_memory_limit_bytes=4096)
    for value in range(1, 5):
        document.apply(_image(value))
    assert document.undo_depth == 4

    document.undo_memory_limit_bytes = 512

    assert document.undo_depth == 2


def test_stored_pixels_are_read_only() -> None:
    document = Document(_image(0))

    assert not document.image.flags.writeable
    with pytest.raises(ValueError, match="read-only"):
        document.image[0, 0, 0] = 1


@pytest.mark.parametrize(
    ("shape", "dtype"),
    [((4, 4, 3), np.uint8), ((4, 4, 4), np.float32)],
)
def test_rejects_invalid_pixels(shape: tuple[int, int, int], dtype: type[np.generic]) -> None:
    with pytest.raises(ValueError, match=r"\(H, W, 4\)"):
        Document(np.zeros(shape, dtype=dtype))


def test_from_file_loads_and_starts_clean(tmp_path: Path) -> None:
    source = tmp_path / "input.png"
    save_png(source, _image(7), 300)

    document = Document.from_file(source, settings=Settings(default_dpi=72))

    assert document.source_path == source
    assert document.dpi == pytest.approx((300.0, 300.0), abs=0.5)
    assert not document.dirty
    assert not document.can_undo
    assert np.array_equal(document.image, _image(7))


def test_from_file_uses_the_settings_default_when_the_file_has_no_dpi(
    tmp_path: Path,
) -> None:
    source = tmp_path / "no-dpi.png"
    Image.new("RGBA", (4, 4), (0, 0, 0, 255)).save(source)

    document = Document.from_file(source, settings=Settings(default_dpi=96))

    assert document.dpi == (96.0, 96.0)
