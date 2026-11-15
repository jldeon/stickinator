"""Application settings that are independent of Qt.

The UI layer persists these with QSettings; core code only ever sees this
dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_DPI = 300.0
DEFAULT_UNDO_MEMORY_LIMIT_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class Settings:
    """User-tunable defaults that affect loading, saving and history."""

    default_dpi: float = DEFAULT_DPI
    undo_memory_limit_bytes: int = DEFAULT_UNDO_MEMORY_LIMIT_BYTES

    def __post_init__(self) -> None:
        if self.default_dpi <= 0:
            msg = "default_dpi must be positive"
            raise ValueError(msg)
        if self.undo_memory_limit_bytes < 0:
            msg = "undo_memory_limit_bytes must not be negative"
            raise ValueError(msg)
