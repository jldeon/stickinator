"""Extend canvas dialog: uniform or per-side margins, in px, % or inches."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox

from stickinator.core.ops.extend_canvas import (
    PER_SIDE,
    UNIFORM,
    ExtendCanvasParams,
)
from stickinator.ui.dialogs.base import ParamsDialog, select_data, spin_box

UNIT_LABELS = (("Pixels", "px"), ("Percent", "percent"), ("Inches", "inches"))


class ExtendCanvasDialog(ParamsDialog[ExtendCanvasParams]):
    def build_form(self) -> None:
        self._mode = QComboBox()
        self._mode.addItem("Uniform", UNIFORM)
        self._mode.addItem("Per side", PER_SIDE)

        self._unit = QComboBox()
        for label, value in UNIT_LABELS:
            self._unit.addItem(label, value)

        self._amount = spin_box()
        self._left = spin_box()
        self._top = spin_box()
        self._right = spin_box()
        self._bottom = spin_box()
        self._centered = QCheckBox("Keep centered")

        for widget, name in (
            (self._mode, "modeCombo"),
            (self._unit, "unitCombo"),
            (self._amount, "amountSpin"),
            (self._left, "leftSpin"),
            (self._top, "topSpin"),
            (self._right, "rightSpin"),
            (self._bottom, "bottomSpin"),
            (self._centered, "centeredCheck"),
        ):
            widget.setObjectName(name)

        self._form.addRow("Mode", self._mode)
        self._form.addRow("Units", self._unit)
        self._form.addRow("Amount", self._amount)
        self._form.addRow("Left", self._left)
        self._form.addRow("Top", self._top)
        self._form.addRow("Right", self._right)
        self._form.addRow("Bottom", self._bottom)
        self._form.addRow("", self._centered)

        self._mode.currentIndexChanged.connect(self._sync_mode)
        self._unit.currentIndexChanged.connect(self._sync_suffixes)

    def set_params(self, params: ExtendCanvasParams) -> None:
        select_data(self._mode, params.mode)
        select_data(self._unit, params.unit)
        self._amount.setValue(params.amount)
        self._left.setValue(params.left)
        self._top.setValue(params.top)
        self._right.setValue(params.right)
        self._bottom.setValue(params.bottom)
        self._centered.setChecked(params.keep_centered)
        self._sync_mode()
        self._sync_suffixes()

    def params(self) -> ExtendCanvasParams:
        return ExtendCanvasParams(
            mode=self._mode.currentData(),
            unit=self._unit.currentData(),
            amount=self._amount.value(),
            left=self._left.value(),
            top=self._top.value(),
            right=self._right.value(),
            bottom=self._bottom.value(),
            keep_centered=self._centered.isChecked(),
        )

    def _sync_mode(self) -> None:
        per_side = self._mode.currentData() == PER_SIDE
        self._form.setRowVisible(self._amount, not per_side)
        for spin in (self._left, self._top, self._right, self._bottom):
            self._form.setRowVisible(spin, per_side)
        self._centered.setEnabled(per_side)

    def _sync_suffixes(self) -> None:
        suffix = {"px": " px", "percent": " %", "inches": " in"}[self._unit.currentData()]
        for spin in (self._amount, self._left, self._top, self._right, self._bottom):
            spin.setSuffix(suffix)
