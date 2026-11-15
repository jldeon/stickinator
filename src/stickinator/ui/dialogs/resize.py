"""Resize / print size dialog, including a DPI-only mode."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox

from stickinator.core.ops.resize import DPI_ONLY, RESIZE, ResizeParams
from stickinator.ui.dialogs.base import ParamsDialog, select_data, spin_box

UNIT_LABELS = (("Pixels", "px"), ("Inches", "inches"), ("Centimetres", "cm"))
RESAMPLING_LABELS = (
    ("Lanczos (best)", "lanczos"),
    ("Bicubic", "bicubic"),
    ("Bilinear", "bilinear"),
    ("Nearest", "nearest"),
)


class ResizeDialog(ParamsDialog[ResizeParams]):
    def build_form(self) -> None:
        self._mode = QComboBox()
        self._mode.addItem("Resize", RESIZE)
        self._mode.addItem("Set DPI only", DPI_ONLY)

        self._unit = QComboBox()
        for label, value in UNIT_LABELS:
            self._unit.addItem(label, value)

        self._width = spin_box()
        self._height = spin_box()
        self._dpi = spin_box(minimum=1.0, maximum=5000.0)
        self._dpi.setSuffix(" dpi")
        self._lock = QCheckBox("Lock aspect ratio")
        self._resampling = QComboBox()
        for label, value in RESAMPLING_LABELS:
            self._resampling.addItem(label, value)

        for widget, name in (
            (self._mode, "modeCombo"),
            (self._unit, "unitCombo"),
            (self._width, "widthSpin"),
            (self._height, "heightSpin"),
            (self._dpi, "dpiSpin"),
            (self._lock, "lockAspectCheck"),
            (self._resampling, "resamplingCombo"),
        ):
            widget.setObjectName(name)

        self._form.addRow("Mode", self._mode)
        self._form.addRow("Units", self._unit)
        self._form.addRow("Width", self._width)
        self._form.addRow("Height", self._height)
        self._form.addRow("Resolution", self._dpi)
        self._form.addRow("", self._lock)
        self._form.addRow("Resampling", self._resampling)

        self._mode.currentIndexChanged.connect(self._sync_mode)

    def set_params(self, params: ResizeParams) -> None:
        select_data(self._mode, params.mode)
        select_data(self._unit, params.unit)
        select_data(self._resampling, params.resampling)
        self._width.setValue(params.width)
        self._height.setValue(params.height)
        self._dpi.setValue(params.dpi)
        self._lock.setChecked(params.lock_aspect)
        self._sync_mode()

    def params(self) -> ResizeParams:
        return ResizeParams(
            mode=self._mode.currentData(),
            unit=self._unit.currentData(),
            width=self._width.value(),
            height=self._height.value(),
            dpi=self._dpi.value(),
            lock_aspect=self._lock.isChecked(),
            resampling=self._resampling.currentData(),
        )

    def _sync_mode(self) -> None:
        resizing = self._mode.currentData() == RESIZE
        for widget in (self._width, self._height, self._unit, self._lock, self._resampling):
            widget.setEnabled(resizing)
