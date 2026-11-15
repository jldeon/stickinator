"""Background removal dialog: colour key / flood fill and GrabCut."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QSpinBox, QWidget

from stickinator.core.ops.bg_algorithmic import (
    AUTO,
    COLOR_KEY,
    CONTIGUOUS,
    GLOBAL,
    GRABCUT,
    PICKED,
    BgRemovalParams,
)
from stickinator.ui.dialogs.base import ParamsDialog, select_data, spin_box
from stickinator.ui.dialogs.widgets import ColorButton

Sample = tuple[tuple[int, int, int], tuple[int, int]]


class ChromaKeyDialog(ParamsDialog[BgRemovalParams]):
    """One dialog for both algorithmic modes, with a live eyedropper."""

    def __init__(
        self,
        title: str,
        params: BgRemovalParams,
        defaults: BgRemovalParams,
        parent: QWidget | None = None,
    ) -> None:
        self._picker: Callable[[], Sample | None] | None = None
        self._seed = (params.seed_x, params.seed_y)
        super().__init__(title, params, defaults, parent)

    def build_form(self) -> None:
        self._method = QComboBox()
        self._method.addItem("Colour key / flood fill", COLOR_KEY)
        self._method.addItem("GrabCut", GRABCUT)

        self._source = QComboBox()
        self._source.addItem("Automatic (edge colour)", AUTO)
        self._source.addItem("Picked colour", PICKED)

        self._color = ColorButton()
        self._pick = QPushButton("Pick on image…")
        self._seed_label = QLabel()

        self._tolerance = spin_box(0.0, 100.0, 1)
        self._mode = QComboBox()
        self._mode.addItem("Contiguous", CONTIGUOUS)
        self._mode.addItem("Global", GLOBAL)
        self._feather = spin_box(0.0, 100.0, 1)
        self._feather.setSuffix(" px")
        self._despeckle = QSpinBox()
        self._despeckle.setRange(0, 100_000)

        self._inset = spin_box(0.0, 100_000.0, 2)
        self._inset_unit = QComboBox()
        self._inset_unit.addItem("Percent", "percent")
        self._inset_unit.addItem("Pixels", "px")
        self._iterations = QSpinBox()
        self._iterations.setRange(1, 20)

        for widget, name in (
            (self._method, "methodCombo"),
            (self._source, "colorSourceCombo"),
            (self._color, "colorButton"),
            (self._pick, "pickButton"),
            (self._seed_label, "seedLabel"),
            (self._tolerance, "toleranceSpin"),
            (self._mode, "modeCombo"),
            (self._feather, "featherSpin"),
            (self._despeckle, "despeckleSpin"),
            (self._inset, "insetSpin"),
            (self._inset_unit, "insetUnitCombo"),
            (self._iterations, "iterationsSpin"),
        ):
            widget.setObjectName(name)

        self._form.addRow("Method", self._method)
        self._form.addRow("Background colour", self._source)
        self._form.addRow("Colour", self._color)
        self._form.addRow("", self._pick)
        self._form.addRow("", self._seed_label)
        self._form.addRow("Tolerance (ΔE)", self._tolerance)
        self._form.addRow("Mode", self._mode)
        self._form.addRow("Edge feather", self._feather)
        self._form.addRow("Despeckle", self._despeckle)
        self._form.addRow("GrabCut inset", self._inset)
        self._form.addRow("Inset units", self._inset_unit)
        self._form.addRow("Iterations", self._iterations)

        self._colour_rows = (
            self._source,
            self._color,
            self._pick,
            self._seed_label,
            self._tolerance,
            self._mode,
            self._feather,
            self._despeckle,
        )
        self._grabcut_rows = (self._inset, self._inset_unit, self._iterations)

        self._method.currentIndexChanged.connect(self._sync_method)
        self._source.currentIndexChanged.connect(self._sync_source)
        self._color.color_changed.connect(self._forget_seed)
        self._pick.clicked.connect(self._pick_colour)

    def set_colour_picker(self, picker: Callable[[], Sample | None]) -> None:
        self._picker = picker

    def set_params(self, params: BgRemovalParams) -> None:
        select_data(self._method, params.method)
        select_data(self._source, params.color_source)
        select_data(self._mode, params.mode)
        select_data(self._inset_unit, params.inset_unit)
        self._color.set_color(params.color)
        self._tolerance.setValue(params.tolerance)
        self._feather.setValue(params.feather)
        self._despeckle.setValue(params.despeckle)
        self._inset.setValue(params.inset)
        self._iterations.setValue(params.iterations)

        self._seed = (params.seed_x, params.seed_y)
        self._update_seed_label()
        self._sync_method()

    def params(self) -> BgRemovalParams:
        return BgRemovalParams(
            method=self._method.currentData(),
            color_source=self._source.currentData(),
            color=self._color.color(),
            tolerance=self._tolerance.value(),
            mode=self._mode.currentData(),
            seed_x=self._seed[0],
            seed_y=self._seed[1],
            feather=self._feather.value(),
            despeckle=self._despeckle.value(),
            inset=self._inset.value(),
            inset_unit=self._inset_unit.currentData(),
            iterations=self._iterations.value(),
        )

    def _sync_method(self) -> None:
        colour_key = self._method.currentData() == COLOR_KEY
        for widget in self._colour_rows:
            self._form.setRowVisible(widget, colour_key)
        for widget in self._grabcut_rows:
            self._form.setRowVisible(widget, not colour_key)
        self._sync_source()

    def _sync_source(self) -> None:
        # Picking is always available: it also switches the source to "picked".
        picked = self._source.currentData() == PICKED
        self._color.setEnabled(picked)

    def _pick_colour(self) -> None:
        if self._picker is None:
            return
        sample = self._picker()
        if sample is None:
            return

        colour, (x, y) = sample
        self._color.set_color(colour)
        self._seed = (x, y)
        select_data(self._source, PICKED)
        self._update_seed_label()
        self._sync_source()

    def _forget_seed(self) -> None:
        self._seed = (-1, -1)
        self._update_seed_label()

    def _update_seed_label(self) -> None:
        if self._seed[0] >= 0 and self._seed[1] >= 0:
            self._seed_label.setText(f"Picked point: x={self._seed[0]}, y={self._seed[1]}")
        else:
            self._seed_label.setText("No point picked")
