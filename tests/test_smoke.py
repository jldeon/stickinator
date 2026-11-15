"""Smoke tests for the milestone 1 shell."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from stickinator.app import APP_NAME, create_application, create_main_window


def test_create_application_is_idempotent(qtbot: QtBot) -> None:
    app = create_application([])

    assert app is QApplication.instance()
    assert app.applicationName() == APP_NAME
    assert app.organizationName() == APP_NAME


def test_main_window_shows(qtbot: QtBot) -> None:
    window = create_main_window()
    qtbot.addWidget(window)

    window.show()

    assert window.isVisible()
    assert window.windowTitle() == APP_NAME
