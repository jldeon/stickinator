"""Headless launch check: start the app, pump the event loop, exit.

Run through ``make smoke``. Never use ``make run`` for verification: that opens a
real window on the developer's desktop.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Import Qt only after the platform is chosen.
from PySide6.QtCore import QTimer

from stickinator.app import create_application, create_main_window

RUN_FOR_MS = 250


def main() -> int:
    app = create_application([])
    window = create_main_window()
    window.show()
    QTimer.singleShot(RUN_FOR_MS, app.quit)

    exit_code = app.exec()
    print("main window launched offscreen")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
