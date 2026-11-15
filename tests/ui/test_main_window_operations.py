"""Main window operation pipeline: run, failure, cancel and enablement."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QPushButton
from pytestqt.qtbot import QtBot
from tests.helpers.fake_ops import FAIL, STUBBORN, FakeParams

from stickinator.core.io import save_png
from stickinator.core.ops.bg_algorithmic import BG_REMOVAL, BgRemovalParams
from stickinator.core.ops.border import BORDER, BorderParams
from stickinator.core.ops.extend_canvas import EXTEND_CANVAS, ExtendCanvasParams
from stickinator.ui.main_window import MainWindow

TIMEOUT_MS = 30_000


def _image(value: int = 10, width: int = 300, height: int = 150) -> np.ndarray:
    image = np.zeros((height, width, 4), dtype=np.uint8)
    image[..., 0] = value
    image[..., 3] = 255
    return image


def _button(window: MainWindow, name: str) -> QPushButton:
    button = window.findChild(QPushButton, name)
    assert button is not None
    return button


def _mark_clean(window: MainWindow) -> None:
    if window.document is not None:
        window.document.mark_saved()


@pytest.fixture
def window(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> MainWindow:
    main_window = MainWindow()
    qtbot.addWidget(main_window, before_close_func=_mark_clean)
    monkeypatch.setattr(main_window, "_show_progress", lambda label: None)
    monkeypatch.setattr(main_window, "_hide_progress", lambda: None)
    return main_window


@pytest.fixture
def source_file(tmp_path: Path) -> Path:
    path = tmp_path / "photo.png"
    save_png(path, _image(), 300)
    return path


def test_wired_buttons_enable_after_loading(window: MainWindow, source_file: Path) -> None:
    window.load_path(source_file)

    assert _button(window, "extendCanvasButton").isEnabled()
    assert _button(window, "trimButton").isEnabled()
    assert _button(window, "resizeButton").isEnabled()
    assert _button(window, "bgAlgorithmicButton").isEnabled()
    assert not _button(window, "bgAiButton").isEnabled()


def test_extend_canvas_runs_and_can_be_undone(
    window: MainWindow, source_file: Path, qtbot: QtBot
) -> None:
    window.load_path(source_file)

    assert window.start_operation(EXTEND_CANVAS, ExtendCanvasParams(amount=10))
    assert window.busy
    qtbot.waitUntil(lambda: not window.busy, timeout=TIMEOUT_MS)

    document = window.document
    assert document is not None
    assert document.image.shape == (170, 320, 4)
    assert document.dirty
    assert _button(window, "undoButton").isEnabled()

    assert window.undo()
    assert document.image.shape == (150, 300, 4)


def test_failure_is_reported_and_pixels_stay_unchanged(
    window: MainWindow, source_file: Path, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.load_path(source_file)
    errors: list[str] = []
    monkeypatch.setattr(window, "_show_error", lambda title, message: errors.append(message))

    assert window.start_operation(FAIL, FakeParams())
    qtbot.waitUntil(lambda: not window.busy, timeout=TIMEOUT_MS)

    assert errors and "RuntimeError: boom" in errors[0]
    document = window.document
    assert document is not None
    assert document.image.shape == (150, 300, 4)
    assert not document.dirty


def test_cancel_leaves_the_document_unchanged(
    window: MainWindow, source_file: Path, qtbot: QtBot
) -> None:
    window.load_path(source_file)

    assert window.start_operation(STUBBORN, FakeParams(delay=30.0))
    qtbot.wait(200)
    window.worker.cancel()
    qtbot.waitUntil(lambda: not window.busy, timeout=TIMEOUT_MS)

    document = window.document
    assert document is not None
    assert document.image.shape == (150, 300, 4)
    assert not document.dirty
    assert _button(window, "extendCanvasButton").isEnabled()


def test_buttons_are_disabled_while_busy(
    window: MainWindow, source_file: Path, qtbot: QtBot
) -> None:
    window.load_path(source_file)

    assert window.start_operation(STUBBORN, FakeParams(delay=30.0))
    assert not _button(window, "openButton").isEnabled()
    assert not _button(window, "saveButton").isEnabled()
    assert not _button(window, "extendCanvasButton").isEnabled()

    window.worker.cancel()
    qtbot.waitUntil(lambda: not window.busy, timeout=TIMEOUT_MS)


def test_border_runs_and_expands_the_canvas(
    window: MainWindow, source_file: Path, qtbot: QtBot
) -> None:
    window.load_path(source_file)

    params = BorderParams(
        width=6,
        outer_outline_only=False,
        merge_pieces=False,
        smooth=False,
        auto_extend=True,
        solid_alpha=True,
    )
    assert window.start_operation(BORDER, params)
    qtbot.waitUntil(lambda: not window.busy, timeout=TIMEOUT_MS)

    document = window.document
    assert document is not None
    assert document.image.shape[0] > 150
    assert set(np.unique(document.image[..., 3]).tolist()) <= {0, 255}


def test_background_removal_runs_end_to_end(
    window: MainWindow, tmp_path: Path, qtbot: QtBot
) -> None:
    image = np.zeros((100, 100, 4), dtype=np.uint8)
    image[...] = (240, 240, 240, 255)
    image[30:70, 30:70] = (200, 40, 40, 255)
    source = tmp_path / "subject.png"
    save_png(source, image, 300)
    window.load_path(source)

    assert window.start_operation(BG_REMOVAL, BgRemovalParams(tolerance=10.0))
    qtbot.waitUntil(lambda: not window.busy, timeout=TIMEOUT_MS)

    document = window.document
    assert document is not None
    assert document.image[0, 0, 3] == 0
    assert document.image[50, 50, 3] == 255
