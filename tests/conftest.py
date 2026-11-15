"""Shared pytest configuration."""

from __future__ import annotations

import os

# Qt must not need a window server, in CI or over SSH. Set before Qt loads.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
