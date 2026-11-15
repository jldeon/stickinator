"""The editable document: pixels, print resolution, dirty state and history."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from stickinator.core.io import RGBAImage, load_image, normalise_dpi
from stickinator.core.settings import (
    DEFAULT_DPI,
    DEFAULT_UNDO_MEMORY_LIMIT_BYTES,
    Settings,
)


@dataclass(frozen=True, slots=True)
class _Snapshot:
    """A previous state. Arrays are shared, never copied again."""

    image: RGBAImage
    dpi: tuple[float, float]
    generation: int


class Document:
    """One image being edited, with a memory-bounded undo history.

    Pixels are always ``(H, W, 4)`` uint8. Arrays handed to the document are
    treated as immutable, which lets snapshots share them; callers must not
    mutate an array after passing it in. The stored array is marked read-only
    to catch mistakes early.
    """

    def __init__(
        self,
        image: RGBAImage,
        dpi: float | Sequence[float] = DEFAULT_DPI,
        *,
        source_path: str | Path | None = None,
        undo_memory_limit_bytes: int = DEFAULT_UNDO_MEMORY_LIMIT_BYTES,
    ) -> None:
        if undo_memory_limit_bytes < 0:
            msg = "undo_memory_limit_bytes must not be negative"
            raise ValueError(msg)

        self._image = _freeze(image)
        self._dpi = normalise_dpi(dpi)
        self._source_path = Path(source_path) if source_path is not None else None
        self._history: list[_Snapshot] = []
        self._history_bytes = 0
        self._memory_limit = undo_memory_limit_bytes
        self._generation = 0
        self._saved_generation = 0

    @classmethod
    def from_file(cls, path: str | Path, *, settings: Settings | None = None) -> Document:
        """Load ``path`` using the supplied settings defaults."""
        active = settings or Settings()
        loaded = load_image(path, default_dpi=active.default_dpi)
        return cls(
            loaded.image,
            loaded.dpi,
            source_path=loaded.source_path,
            undo_memory_limit_bytes=active.undo_memory_limit_bytes,
        )

    @property
    def image(self) -> RGBAImage:
        return self._image

    @property
    def dpi(self) -> tuple[float, float]:
        return self._dpi

    @property
    def source_path(self) -> Path | None:
        return self._source_path

    @property
    def dirty(self) -> bool:
        """True when the pixels or DPI differ from the last saved state."""
        return self._generation != self._saved_generation

    @property
    def can_undo(self) -> bool:
        return bool(self._history)

    @property
    def undo_depth(self) -> int:
        return len(self._history)

    @property
    def undo_memory_bytes(self) -> int:
        return self._history_bytes

    @property
    def undo_memory_limit_bytes(self) -> int:
        return self._memory_limit

    @undo_memory_limit_bytes.setter
    def undo_memory_limit_bytes(self, limit: int) -> None:
        if limit < 0:
            msg = "undo_memory_limit_bytes must not be negative"
            raise ValueError(msg)
        self._memory_limit = limit
        if limit == 0:
            self._history.clear()
            self._history_bytes = 0
        else:
            self._trim_to_limit()

    def apply(
        self,
        image: RGBAImage,
        *,
        dpi: float | Sequence[float] | None = None,
    ) -> None:
        """Replace the document contents, pushing the old state onto the history."""
        new_image = _freeze(image)
        new_dpi = self._dpi if dpi is None else normalise_dpi(dpi)

        self._push(_Snapshot(self._image, self._dpi, self._generation))
        self._generation += 1
        self._image = new_image
        self._dpi = new_dpi

    def set_dpi(self, dpi: float | Sequence[float]) -> None:
        """ "Set DPI only": change print resolution without touching the pixels."""
        self.apply(self._image, dpi=dpi)

    def undo(self) -> bool:
        """Restore the previous state. Returns False when there is nothing to undo."""
        if not self._history:
            return False

        snapshot = self._history.pop()
        self._history_bytes -= snapshot.image.nbytes
        self._image = snapshot.image
        self._dpi = snapshot.dpi
        self._generation = snapshot.generation
        return True

    def mark_saved(self, path: str | Path | None = None) -> None:
        """Record that the current state is on disk."""
        if path is not None:
            self._source_path = Path(path)
        self._saved_generation = self._generation

    def _push(self, snapshot: _Snapshot) -> None:
        if self._memory_limit <= 0:
            return
        self._history.append(snapshot)
        self._history_bytes += snapshot.image.nbytes
        self._trim_to_limit()

    def _trim_to_limit(self) -> None:
        # Keep at least one step whenever history is enabled, even if a single
        # image is larger than the configured cap.
        while self._history_bytes > self._memory_limit and len(self._history) > 1:
            oldest = self._history.pop(0)
            self._history_bytes -= oldest.image.nbytes


def _freeze(image: RGBAImage) -> RGBAImage:
    array = np.asarray(image)
    if array.dtype != np.uint8 or array.ndim != 3 or array.shape[2] != 4:
        msg = "image must be an (H, W, 4) uint8 array"
        raise ValueError(msg)

    array = np.ascontiguousarray(array)
    array.setflags(write=False)
    return array
