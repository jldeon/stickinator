"""Dialogs for extend canvas, trim and resize."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QPushButton,
    QSpinBox,
    QWidget,
)
from pytestqt.qtbot import QtBot

from stickinator.core.ops.bg_ai import BgAiParams
from stickinator.core.ops.bg_algorithmic import (
    GLOBAL,
    GRABCUT,
    PICKED,
    BgRemovalParams,
)
from stickinator.core.ops.border import HULL, BorderParams
from stickinator.core.ops.extend_canvas import (
    PER_SIDE,
    ExtendCanvasParams,
)
from stickinator.core.ops.resize import DPI_ONLY, ResizeParams
from stickinator.core.ops.trim import TrimParams
from stickinator.ui.dialogs.bg_ai import BgAiDialog
from stickinator.ui.dialogs.bg_algorithmic import ChromaKeyDialog
from stickinator.ui.dialogs.border import BorderDialog
from stickinator.ui.dialogs.extend_canvas import ExtendCanvasDialog
from stickinator.ui.dialogs.resize import ResizeDialog
from stickinator.ui.dialogs.trim import TrimDialog
from stickinator.ui.dialogs.widgets import ColorButton


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


def test_border_dialog_round_trips_all_fields(qtbot: QtBot) -> None:
    params = BorderParams(
        width=0.25,
        unit="inches",
        color=(12, 34, 56),
        alpha_threshold=64,
        outer_outline_only=False,
        merge_pieces=True,
        merge_method=HULL,
        merge_radius=5,
        smooth=False,
        smoothing=3,
        solid_alpha=False,
        auto_extend=False,
    )
    dialog = BorderDialog("Border", params, BorderParams())
    qtbot.addWidget(dialog)

    assert dialog.params() == params


def test_border_dialog_reset_restores_defaults(qtbot: QtBot) -> None:
    dialog = BorderDialog(
        "Border",
        BorderParams(width=40, color=(0, 0, 0), smooth=False),
        BorderParams(),
    )
    qtbot.addWidget(dialog)

    dialog.reset()

    assert dialog.params() == BorderParams()


def test_border_dialog_disables_merge_controls_when_off(qtbot: QtBot) -> None:
    params = BorderParams(merge_pieces=False)
    dialog = BorderDialog("Border", params, BorderParams())
    qtbot.addWidget(dialog)
    radius = _child(dialog, QDoubleSpinBox, "radiusSpin")
    method = _child(dialog, QComboBox, "mergeMethodCombo")

    assert not method.isEnabled()
    assert not radius.isEnabled()

    merge = _child(dialog, QCheckBox, "mergeCheck")
    merge.setChecked(True)
    assert method.isEnabled()
    assert radius.isEnabled()

    method.setCurrentIndex(method.findData(HULL))
    assert not radius.isEnabled()
    assert dialog.params().merge_method == HULL


def test_border_dialog_uses_the_colour_button(qtbot: QtBot) -> None:
    dialog = BorderDialog("Border", BorderParams(), BorderParams())
    qtbot.addWidget(dialog)
    button = _child(dialog, ColorButton, "colorButton")

    button.set_color((1, 2, 3))

    assert dialog.params().color == (1, 2, 3)


def test_background_dialog_round_trips_all_fields(qtbot: QtBot) -> None:
    params = BgRemovalParams(
        method=GRABCUT,
        color_source=PICKED,
        color=(1, 2, 3),
        tolerance=12.5,
        mode=GLOBAL,
        seed_x=3,
        seed_y=4,
        feather=2.5,
        despeckle=30,
        inset=10,
        inset_unit="px",
        iterations=7,
    )
    dialog = ChromaKeyDialog("Remove BG", params, BgRemovalParams())
    qtbot.addWidget(dialog)

    assert dialog.params() == params


def test_background_dialog_switches_between_methods(qtbot: QtBot) -> None:
    dialog = ChromaKeyDialog("Remove BG", BgRemovalParams(), BgRemovalParams())
    qtbot.addWidget(dialog)
    tolerance = _child(dialog, QDoubleSpinBox, "toleranceSpin")
    inset = _child(dialog, QDoubleSpinBox, "insetSpin")
    assert dialog._form.isRowVisible(tolerance)
    assert not dialog._form.isRowVisible(inset)

    method = _child(dialog, QComboBox, "methodCombo")
    method.setCurrentIndex(method.findData(GRABCUT))

    assert not dialog._form.isRowVisible(tolerance)
    assert dialog._form.isRowVisible(inset)


def test_background_dialog_picker_sets_colour_seed_and_source(qtbot: QtBot) -> None:
    dialog = ChromaKeyDialog("Remove BG", BgRemovalParams(), BgRemovalParams())
    qtbot.addWidget(dialog)
    dialog.set_colour_picker(lambda: ((9, 8, 7), (11, 12)))

    _child(dialog, QPushButton, "pickButton").click()

    params = dialog.params()
    assert params.color == (9, 8, 7)
    assert (params.seed_x, params.seed_y) == (11, 12)
    assert params.color_source == PICKED


def test_background_dialog_reset_restores_defaults(qtbot: QtBot) -> None:
    dialog = ChromaKeyDialog(
        "Remove BG",
        BgRemovalParams(tolerance=50, seed_x=1, seed_y=2, color=(0, 0, 0)),
        BgRemovalParams(),
    )
    qtbot.addWidget(dialog)

    dialog.reset()

    assert dialog.params() == BgRemovalParams()


def test_ai_dialog_round_trips_and_toggles_binarize(qtbot: QtBot) -> None:
    params = BgAiParams(provider="openai", binarize=True, threshold=90)
    dialog = BgAiDialog("Remove BG (AI)", params, BgAiParams())
    qtbot.addWidget(dialog)

    assert dialog.params() == params

    binarize = _child(dialog, QCheckBox, "binarizeCheck")
    threshold = _child(dialog, QSpinBox, "thresholdSpin")
    assert threshold.isEnabled()

    binarize.setChecked(False)
    assert not threshold.isEnabled()
