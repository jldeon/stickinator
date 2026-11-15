"""Application wiring: QApplication, main window, and the GUI entry point."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication, QMainWindow

from stickinator import __version__

APP_NAME = "Stickinator"
ORG_NAME = "Stickinator"
ORG_DOMAIN = "stickinator.app"

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    """Return the process-wide QApplication, configured with the app identity."""
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        app = existing
    else:
        app = QApplication(list(argv) if argv is not None else sys.argv)

    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setOrganizationDomain(ORG_DOMAIN)
    app.setApplicationVersion(__version__)
    return app


def create_main_window() -> QMainWindow:
    """Build the top-level window.

    Milestone 1 ships an empty shell; the preview and button column arrive in
    milestone 3.
    """
    window = QMainWindow()
    window.setWindowTitle(APP_NAME)
    window.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
    return window


def main(argv: Sequence[str] | None = None) -> int:
    """Run the GUI. Returns the process exit code."""
    app = create_application(argv)
    window = create_main_window()
    window.show()
    return app.exec()
