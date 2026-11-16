"""Settings dialog: persistence, keychain writes and warnings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QComboBox, QGroupBox, QLineEdit, QSpinBox
from pytestqt.qtbot import QtBot

from stickinator.core.ai.config import HTTP, OPENAI
from stickinator.ui.dialogs import settings_dialog
from stickinator.ui.dialogs.settings_dialog import SettingsDialog
from stickinator.ui.settings_store import AppSettingsStore

MEGABYTE = 1024 * 1024


@pytest.fixture
def setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[AppSettingsStore, dict[str, str]]:
    qsettings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    qsettings.clear()
    keys: dict[str, str] = {}

    def get_key(provider: str) -> str:
        return keys.get(provider, "")

    def set_key(provider: str, value: str) -> bool:
        keys[provider] = value
        return True

    monkeypatch.setattr(settings_dialog, "get_api_key", get_key)
    monkeypatch.setattr(settings_dialog, "set_api_key", set_key)
    return AppSettingsStore(qsettings), keys


def _child(dialog: SettingsDialog, kind: type[Any], name: str) -> Any:
    widget = dialog.findChild(kind, name)
    assert widget is not None
    return widget


def test_saves_ai_and_general_values(
    qtbot: QtBot, setup: tuple[AppSettingsStore, dict[str, str]]
) -> None:
    store, keys = setup
    dialog = SettingsDialog(store)
    qtbot.addWidget(dialog)

    provider = _child(dialog, QComboBox, "providerCombo")
    provider.setCurrentIndex(provider.findData(HTTP))
    _child(dialog, QLineEdit, "httpUrlEdit").setText("https://remove.example/api")
    _child(dialog, QLineEdit, "httpKeyEdit").setText("secret")
    _child(dialog, QSpinBox, "undoLimitSpin").setValue(64)
    dialog.accept()

    ai = store.load_ai()
    assert ai.provider == HTTP
    assert ai.http_url == "https://remove.example/api"
    assert store.load_general().undo_memory_limit_bytes == 64 * MEGABYTE
    assert keys[HTTP] == "secret"


def test_saves_the_openai_key(qtbot: QtBot, setup: tuple[AppSettingsStore, dict[str, str]]) -> None:
    store, keys = setup
    dialog = SettingsDialog(store)
    qtbot.addWidget(dialog)
    _child(dialog, QLineEdit, "openaiKeyEdit").setText("sk-test")

    dialog.accept()

    assert keys[OPENAI] == "sk-test"
    assert store.load_ai().provider == "local"


def test_ai_tab_uses_two_columns(
    qtbot: QtBot, setup: tuple[AppSettingsStore, dict[str, str]]
) -> None:
    store, _ = setup
    dialog = SettingsDialog(store)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.wait(10)

    panels = {box.title(): box for box in dialog.findChildren(QGroupBox)}
    assert panels["Local (rembg)"].x() < panels["Generic HTTP endpoint"].x()
    assert panels["Local (rembg)"].x() < panels["OpenAI-compatible edits"].x()
    # The taller single-column layout did not fit a laptop screen.
    assert dialog.height() < dialog.width()


def test_warns_when_the_keychain_is_unavailable(
    qtbot: QtBot,
    setup: tuple[AppSettingsStore, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _ = setup
    monkeypatch.setattr(settings_dialog, "set_api_key", lambda provider, value: False)
    dialog = SettingsDialog(store)
    qtbot.addWidget(dialog)
    warnings: list[str] = []
    monkeypatch.setattr(dialog, "_warn", lambda title, message: warnings.append(title))
    _child(dialog, QLineEdit, "httpKeyEdit").setText("secret")

    dialog.accept()

    assert warnings == ["Keychain unavailable"]
