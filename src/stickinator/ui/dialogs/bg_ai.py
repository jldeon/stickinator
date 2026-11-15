"""AI background removal dialog: provider override and alpha clean-up."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QSpinBox

from stickinator.core.ai.config import HTTP, LOCAL, OPENAI
from stickinator.core.ops.bg_ai import BgAiParams
from stickinator.ui.dialogs.base import ParamsDialog, select_data


class BgAiDialog(ParamsDialog[BgAiParams]):
    def build_form(self) -> None:
        self._provider = QComboBox()
        self._provider.addItem("Local (rembg, offline)", LOCAL)
        self._provider.addItem("Generic HTTP endpoint", HTTP)
        self._provider.addItem("OpenAI-compatible edits", OPENAI)
        self._provider.setObjectName("providerCombo")

        self._binarize = QCheckBox("Binarize alpha")
        self._binarize.setObjectName("binarizeCheck")
        self._threshold = QSpinBox()
        self._threshold.setRange(0, 255)
        self._threshold.setObjectName("thresholdSpin")

        self._form.addRow("Provider", self._provider)
        self._form.addRow("", self._binarize)
        self._form.addRow("Binarize threshold", self._threshold)

        self._binarize.toggled.connect(self._threshold.setEnabled)

    def set_params(self, params: BgAiParams) -> None:
        select_data(self._provider, params.provider)
        self._binarize.setChecked(params.binarize)
        self._threshold.setValue(params.threshold)
        self._threshold.setEnabled(params.binarize)

    def params(self) -> BgAiParams:
        return BgAiParams(
            provider=self._provider.currentData(),
            binarize=self._binarize.isChecked(),
            threshold=self._threshold.value(),
        )
