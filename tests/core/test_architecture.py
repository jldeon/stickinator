"""Architectural invariants that are easy to break by accident."""

from __future__ import annotations

import subprocess
import sys


def test_core_package_does_not_import_qt() -> None:
    """`core` must stay UI-free so it can be tested and reused headlessly."""
    code = (
        "import sys;"
        "import stickinator.core.image_doc, stickinator.core.io, stickinator.core.settings;"
        "print(any(name.split('.')[0] == 'PySide6' for name in sys.modules))"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "False"
