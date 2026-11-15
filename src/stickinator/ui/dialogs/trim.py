"""Trim dialog: alpha threshold and optional margin."""

from __future__ import annotations

from PySide6.QtWidgets import QSpinBox

from stickinator.core.ops.trim import TrimParams
from stickinator.ui.dialogs.base import ParamsDialog


class TrimDialog(ParamsDialog[TrimParams]):
    def build_form(self) -> None:
        self._threshold = QSpinBox()
        self._threshold.setRange(0, 255)

        self._margin = QSpinBox()
        self._margin.setRange(0, 100_000)

        self._threshold.setObjectName("thresholdSpin")
        self._margin.setObjectName("marginSpin")

        self._form.addRow("Content threshold", self._threshold)
        self._form.addRow("Margin (px)", self._margin)

    def set_params(self, params: TrimParams) -> None:
        self._threshold.setValue(params.threshold)
        self._margin.setValue(params.margin)

    def params(self) -> TrimParams:
        return TrimParams(
            threshold=self._threshold.value(),
            margin=self._margin.value(),
        )
