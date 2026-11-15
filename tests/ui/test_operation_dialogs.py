"""Dialogs for extend canvas, trim and resize."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox, QWidget
from pytestqt.qtbot import QtBot

from stickinator.core.ops.extend_canvas import (
    PER_SIDE,
    ExtendCanvasParams,
)
from stickinator.core.ops.resize import DPI_ONLY, ResizeParams
from stickinator.core.ops.trim import TrimParams
from stickinator.ui.dialogs.extend_canvas import ExtendCanvasDialog
from stickinator.ui.dialogs.resize import ResizeDialog
from stickinator.ui.dialogs.trim import TrimDialog


def _child(dialog: QWidget, kind: type[Any], name: str) -> Any:
    widget = dialog.findChild(kind, name)
    assert widget is not None
    return widget


def test_extend_dialog_round_trips_all_fields(qtbot: QtBot) -> None:
    params = ExtendCanvasParams(
        mode=PER_SIDE,
        unit="inches",
        amount=3,
        left=1,
        top=2,
        right=3,
        bottom=4,
        keep_centered=False,
    )
    dialog = ExtendCanvasDialog("Extend", params, ExtendCanvasParams())
    qtbot.addWidget(dialog)

    assert dialog.params() == params


def test_extend_dialog_reset_restores_defaults(qtbot: QtBot) -> None:
    dialog = ExtendCanvasDialog(
        "Extend",
        ExtendCanvasParams(mode=PER_SIDE, unit="percent", left=50),
        ExtendCanvasParams(),
    )
    qtbot.addWidget(dialog)

    dialog.reset()

    assert dialog.params() == ExtendCanvasParams()


def test_extend_dialog_swaps_uniform_and_per_side_rows(qtbot: QtBot) -> None:
    dialog = ExtendCanvasDialog("Extend", ExtendCanvasParams(), ExtendCanvasParams())
    qtbot.addWidget(dialog)
    amount = _child(dialog, QDoubleSpinBox, "amountSpin")
    left = _child(dialog, QDoubleSpinBox, "leftSpin")

    assert dialog._form.isRowVisible(amount)
    assert not dialog._form.isRowVisible(left)

    mode = _child(dialog, QComboBox, "modeCombo")
    mode.setCurrentIndex(mode.findData(PER_SIDE))

    assert not dialog._form.isRowVisible(amount)
    assert dialog._form.isRowVisible(left)


def test_trim_dialog_round_trips_and_resets(qtbot: QtBot) -> None:
    params = TrimParams(threshold=64, margin=12)
    dialog = TrimDialog("Trim", params, TrimParams())
    qtbot.addWidget(dialog)

    assert dialog.params() == params

    dialog.reset()

    assert dialog.params() == TrimParams()


def test_resize_dialog_round_trips(qtbot: QtBot) -> None:
    params = ResizeParams(
        unit="inches",
        width=4,
        height=6,
        dpi=150,
        lock_aspect=False,
        resampling="nearest",
    )
    dialog = ResizeDialog("Resize", params, ResizeParams())
    qtbot.addWidget(dialog)

    assert dialog.params() == params


def test_resize_dialog_disables_size_fields_in_dpi_only_mode(qtbot: QtBot) -> None:
    dialog = ResizeDialog("Resize", ResizeParams(mode=DPI_ONLY), ResizeParams())
    qtbot.addWidget(dialog)

    width = _child(dialog, QDoubleSpinBox, "widthSpin")
    dpi = _child(dialog, QDoubleSpinBox, "dpiSpin")
    assert not width.isEnabled()
    assert dpi.isEnabled()

    mode = _child(dialog, QComboBox, "modeCombo")
    mode.setCurrentIndex(mode.findData("resize"))

    assert width.isEnabled()


def test_resize_dialog_reset_restores_defaults(qtbot: QtBot) -> None:
    dialog = ResizeDialog("Resize", ResizeParams(width=500, height=500, dpi=72), ResizeParams())
    qtbot.addWidget(dialog)

    dialog.reset()

    assert dialog.params() == ResizeParams()


def test_trim_spin_boxes_are_wired(qtbot: QtBot) -> None:
    dialog = TrimDialog("Trim", TrimParams(), TrimParams())
    qtbot.addWidget(dialog)

    threshold = _child(dialog, QSpinBox, "thresholdSpin")
    margin = _child(dialog, QSpinBox, "marginSpin")

    threshold.setValue(10)
    margin.setValue(7)

    assert dialog.params() == TrimParams(threshold=10, margin=7)
