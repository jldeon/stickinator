"""Network-marked integration test: downloads a rembg model on first run.

Excluded from CI and from ``make test``; run with ``make test-network``.
"""

from __future__ import annotations

import numpy as np
import pytest

from stickinator.core.ai import local_rembg
from stickinator.core.ai.config import LocalConfig
from stickinator.core.ops.base import NeverCancelled


@pytest.mark.network
def test_local_rembg_removes_a_synthetic_background() -> None:
    image = np.zeros((64, 64, 4), dtype=np.uint8)
    image[...] = (240, 240, 240, 255)
    image[16:48, 16:48] = (200, 40, 40, 255)

    result = local_rembg.remove_background(image, LocalConfig(model="u2net"), NeverCancelled())

    assert result.shape == (64, 64, 4)
    assert result[0, 0, 3] < 64
    assert result[32, 32, 3] > 191
