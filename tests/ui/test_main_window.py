"""Main window: enablement, file actions, drag-and-drop and close guards."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QMimeData, QPointF, QSettings, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QLabel, QPushButton
from pytestqt.qtbot import QtBot

from stickinator.core.io import load_image, save_png
from stickinator.ui.main_window import MainWindow, UnsavedChoice
from stickinator.ui.settings_store import AppSettingsStore

OPERATION_BUTTONS = (
    "bgAlgorithmicButton",
    "bgAiButton",
    "extendCanvasButton",
    "borderButton",
    "trimButton",
    "resizeButton",
)


def _image(value: int = 0, width: int = 100, height: int = 50) -> np.ndarray:
    image = np.zeros((height, width, 4), dtype=np.uint8)
    image[..., 0] = value
    image[..., 3] = 255
    return image


def _button(window: MainWindow, name: str) -> QPushButton:
    button = window.findChild(QPushButton, name)
    assert button is not None
    return button


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    store = AppSettingsStore(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    main_window = MainWindow(app_store=store)
    # A dirty document left behind by a test must not open a real prompt during
    # pytest-qt's teardown, where monkeypatched dialogs are already gone.
    qtbot.addWidget(main_window, before_close_func=_mark_clean)
    return main_window


def _mark_clean(window: MainWindow) -> None:
    if window.document is not None:
        window.document.mark_saved()


@pytest.fixture
def source_file(tmp_path: Path) -> Path:
    path = tmp_path / "photo.png"
    save_png(path, _image(10, 300, 150), 300)
    return path


def test_only_open_is_enabled_initially(window: MainWindow) -> None:
    assert _button(window, "openButton").isEnabled()
    assert not _button(window, "saveButton").isEnabled()
    assert not _button(window, "undoButton").isEnabled()
    for name in OPERATION_BUTTONS:
        assert not _button(window, name).isEnabled()


def test_loading_updates_status_title_and_buttons(window: MainWindow, source_file: Path) -> None:
    assert window.load_path(source_file)

    assert window.document is not None
    status = window.findChild(QLabel, "statusLabel")
    assert status is not None
    assert "300 x 150 px" in status.text()
    assert "300 DPI" in status.text()
    assert "1.00 x 0.50 in" in status.text()
    assert "2.54 x 1.27 cm" in status.text()
    assert "photo.png" in window.windowTitle()
    assert not window.isWindowModified()
    assert _button(window, "saveButton").isEnabled()
    assert not _button(window, "undoButton").isEnabled()


def test_open_file_uses_the_selected_path(
    window: MainWindow, source_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(window, "_ask_open_path", lambda: source_file)

    assert window.open_file()

    assert window.document is not None
    assert window.document.source_path == source_file


def test_load_failure_is_reported_and_changes_nothing(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / "broken.png"
    broken.write_text("not an image")
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(
        window, "_show_error", lambda title, message: errors.append((title, message))
    )

    assert not window.load_path(broken)

    assert window.document is None
    assert errors
    assert errors[0][0] == "Could not open image"


def test_save_as_suggests_a_sticker_name_and_writes_png(
    window: MainWindow,
    source_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window.load_path(source_file)
    destination = tmp_path / "photo_sticker.png"
    suggestions: list[Path] = []

    def choose(suggested: Path) -> Path:
        suggestions.append(suggested)
        return destination

    monkeypatch.setattr(window, "_ask_save_path", choose)

    assert window.save()

    assert suggestions == [source_file.with_name("photo_sticker.png")]
    assert destination.exists()
    assert load_image(destination).dpi == pytest.approx((300.0, 300.0), abs=0.5)
    document = window.document
    assert document is not None
    assert not document.dirty


def test_save_reuses_the_first_path_without_asking_again(
    window: MainWindow,
    source_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window.load_path(source_file)
    destination = tmp_path / "sticker.png"
    monkeypatch.setattr(window, "_ask_save_path", lambda suggested: destination)
    assert window.save()

    document = window.document
    assert document is not None
    document.apply(_image(99, 300, 150))

    def explode(suggested: Path) -> Path:
        raise AssertionError("save dialog should not be shown again")

    monkeypatch.setattr(window, "_ask_save_path", explode)

    assert window.save()
    assert load_image(destination).image[0, 0, 0] == 99


def test_undo_restores_the_previous_state(window: MainWindow, source_file: Path) -> None:
    window.load_path(source_file)
    document = window.document
    assert document is not None
    document.apply(_image(99, 300, 150))

    assert window.undo()

    assert np.array_equal(document.image, _image(10, 300, 150))
    assert not _button(window, "undoButton").isEnabled()


def test_saving_over_the_original_asks_first(
    window: MainWindow, source_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.load_path(source_file)
    asked: list[Path] = []
    monkeypatch.setattr(window, "_ask_save_path", lambda suggested: source_file)

    def refuse(original: Path) -> bool:
        asked.append(original)
        return False

    monkeypatch.setattr(window, "_confirm_overwrite_original", refuse)

    assert not window.save()

    assert asked == [source_file]
    assert load_image(source_file).image.shape == (150, 300, 4)


def test_cancel_keeps_the_window_open(
    window: MainWindow, source_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.load_path(source_file)
    document = window.document
    assert document is not None
    document.apply(_image(1))
    monkeypatch.setattr(window, "_ask_unsaved_changes", lambda: UnsavedChoice.CANCEL)
    window.show()

    assert not window.close()


def test_discard_closes_without_saving(
    window: MainWindow, source_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.load_path(source_file)
    document = window.document
    assert document is not None
    document.apply(_image(1))
    monkeypatch.setattr(window, "_ask_unsaved_changes", lambda: UnsavedChoice.DISCARD)
    window.show()

    assert window.close()


def test_save_choice_writes_before_closing(
    window: MainWindow,
    source_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window.load_path(source_file)
    document = window.document
    assert document is not None
    document.apply(_image(1))
    destination = tmp_path / "saved.png"
    monkeypatch.setattr(window, "_ask_unsaved_changes", lambda: UnsavedChoice.SAVE)
    monkeypatch.setattr(window, "_ask_save_path", lambda suggested: destination)
    window.show()

    assert window.close()

    assert destination.exists()
    assert not document.dirty


def test_cancelled_prompt_prevents_opening_another_file(
    window: MainWindow, source_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.load_path(source_file)
    document = window.document
    assert document is not None
    document.apply(_image(1))
    monkeypatch.setattr(window, "_ask_unsaved_changes", lambda: UnsavedChoice.CANCEL)
    dialog_calls: list[int] = []
    monkeypatch.setattr(window, "_ask_open_path", lambda: dialog_calls.append(1))

    assert not window.open_file()

    assert dialog_calls == []
    assert document.source_path == source_file


def test_drop_loads_a_supported_file(window: MainWindow, source_file: Path) -> None:
    event, mime = _drop_event(source_file)

    window.dropEvent(event)

    assert mime.hasUrls()
    assert event.isAccepted()
    assert window.document is not None
    assert window.document.source_path == source_file


def test_drop_ignores_unsupported_files(window: MainWindow, tmp_path: Path) -> None:
    unsupported = tmp_path / "picture.bmp"
    unsupported.write_bytes(b"BM")
    event, mime = _drop_event(unsupported)

    window.dropEvent(event)

    assert mime.hasUrls()
    assert not event.isAccepted()
    assert window.document is None


def test_drag_enter_accepts_supported_files_and_rejects_others(
    window: MainWindow, source_file: Path, tmp_path: Path
) -> None:
    unsupported = tmp_path / "picture.bmp"
    unsupported.write_bytes(b"BM")

    accepted, accepted_mime = _drag_enter_event(window, source_file)
    rejected, rejected_mime = _drag_enter_event(window, unsupported)

    assert accepted_mime.hasUrls()
    assert rejected_mime.hasUrls()
    assert accepted.isAccepted()
    assert not rejected.isAccepted()


def _mime(path: Path) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    return mime


def _drop_event(path: Path) -> tuple[QDropEvent, QMimeData]:
    # The caller must keep the mime data alive: QDropEvent only holds a pointer.
    mime = _mime(path)
    event = QDropEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    return event, mime


def _drag_enter_event(window: MainWindow, path: Path) -> tuple[QDragEnterEvent, QMimeData]:
    mime = _mime(path)
    event = QDragEnterEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    # Qt normally dispatches this; call the handler the same way it would.
    window.dragEnterEvent(event)
    return event, mime
