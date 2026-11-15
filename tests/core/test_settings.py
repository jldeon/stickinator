"""Settings validation."""

from __future__ import annotations

import pytest

from stickinator.core.settings import Settings


def test_rejects_non_positive_default_dpi() -> None:
    with pytest.raises(ValueError, match="default_dpi"):
        Settings(default_dpi=0)


def test_rejects_negative_undo_limit() -> None:
    with pytest.raises(ValueError, match="undo_memory_limit_bytes"):
        Settings(undo_memory_limit_bytes=-1)
