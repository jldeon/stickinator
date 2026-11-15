"""Application wiring: QApplication and the GUI entry point."""

from __future__ import annotations

import multiprocessing
import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from stickinator import APP_NAME, ORG_DOMAIN, ORG_NAME, __version__
from stickinator.ui.main_window import MainWindow


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


def create_main_window() -> MainWindow:
    """Build the top-level window."""
    return MainWindow()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the GUI, or the headless self-test. Returns the process exit code."""
    # Required for the spawned worker processes in a frozen bundle.
    multiprocessing.freeze_support()

    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in arguments:
        from pathlib import Path

        from stickinator.diagnostics import run_self_test

        report_path = None
        if "--self-test-out" in arguments:
            index = arguments.index("--self-test-out")
            if index + 1 < len(arguments):
                report_path = Path(arguments[index + 1])
        return run_self_test(use_ai="--ai" in arguments, report_path=report_path)

    app = create_application(argv)
    window = create_main_window()
    window.show()
    return app.exec()
