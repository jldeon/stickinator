"""Border dialog: width, colour, outline clean-up and solid alpha."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QSpinBox

from stickinator.core.ops.border import CLOSE, HULL, BorderParams
from stickinator.ui.dialogs.base import ParamsDialog, select_data, spin_box
from stickinator.ui.dialogs.widgets import ColorButton

UNIT_LABELS = (("Pixels", "px"), ("Inches", "inches"))
MERGE_LABELS = (("Close gaps", CLOSE), ("Convex hull", HULL))


class BorderDialog(ParamsDialog[BorderParams]):
    def build_form(self) -> None:
        self._width = spin_box()
        self._unit = QComboBox()
        for label, value in UNIT_LABELS:
            self._unit.addItem(label, value)

        self._color = ColorButton()
        self._threshold = QSpinBox()
        self._threshold.setRange(0, 255)

        self._outer = QCheckBox("Outer outline only (fill holes)")
        self._merge = QCheckBox("Merge separate pieces")
        self._merge_method = QComboBox()
        for label, value in MERGE_LABELS:
            self._merge_method.addItem(label, value)
        self._radius = spin_box(maximum=500.0)
        self._radius.setSuffix(" px")

        self._smooth = QCheckBox("Smooth / rounded outline")
        self._smoothing = spin_box(maximum=100.0)
        self._solid = QCheckBox("Solid alpha")
        self._auto_extend = QCheckBox("Auto-extend canvas")

        for widget, name in (
            (self._width, "widthSpin"),
            (self._unit, "unitCombo"),
            (self._color, "colorButton"),
            (self._threshold, "thresholdSpin"),
            (self._outer, "outerCheck"),
            (self._merge, "mergeCheck"),
            (self._merge_method, "mergeMethodCombo"),
            (self._radius, "radiusSpin"),
            (self._smooth, "smoothCheck"),
            (self._smoothing, "smoothingSpin"),
            (self._solid, "solidCheck"),
            (self._auto_extend, "autoExtendCheck"),
        ):
            widget.setObjectName(name)

        self._form.addRow("Width", self._width)
        self._form.addRow("Units", self._unit)
        self._form.addRow("Colour", self._color)
        self._form.addRow("Content threshold", self._threshold)
        self._form.addRow("", self._outer)
        self._form.addRow("", self._merge)
        self._form.addRow("Merge method", self._merge_method)
        self._form.addRow("Merge radius", self._radius)
        self._form.addRow("", self._smooth)
        self._form.addRow("Smoothing", self._smoothing)
        self._form.addRow("", self._solid)
        self._form.addRow("", self._auto_extend)

        self._merge.toggled.connect(self._sync_controls)
        self._merge_method.currentIndexChanged.connect(self._sync_controls)
        self._smooth.toggled.connect(self._sync_controls)

    def set_params(self, params: BorderParams) -> None:
        select_data(self._unit, params.unit)
        select_data(self._merge_method, params.merge_method)
        self._width.setValue(params.width)
        self._color.set_color(params.color)
        self._threshold.setValue(params.alpha_threshold)
        self._outer.setChecked(params.outer_outline_only)
        self._merge.setChecked(params.merge_pieces)
        self._radius.setValue(params.merge_radius)
        self._smooth.setChecked(params.smooth)
        self._smoothing.setValue(params.smoothing)
        self._solid.setChecked(params.solid_alpha)
        self._auto_extend.setChecked(params.auto_extend)
        self._sync_controls()

    def params(self) -> BorderParams:
        return BorderParams(
            width=self._width.value(),
            unit=self._unit.currentData(),
            color=self._color.color(),
            alpha_threshold=self._threshold.value(),
            outer_outline_only=self._outer.isChecked(),
            merge_pieces=self._merge.isChecked(),
            merge_method=self._merge_method.currentData(),
            merge_radius=self._radius.value(),
            smooth=self._smooth.isChecked(),
            smoothing=self._smoothing.value(),
            solid_alpha=self._solid.isChecked(),
            auto_extend=self._auto_extend.isChecked(),
        )

    def _sync_controls(self) -> None:
        merging = self._merge.isChecked()
        self._merge_method.setEnabled(merging)
        self._radius.setEnabled(merging and self._merge_method.currentData() == CLOSE)
        self._smoothing.setEnabled(self._smooth.isChecked())
