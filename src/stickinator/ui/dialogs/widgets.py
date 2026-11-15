"""Small reusable dialog widgets."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QPushButton, QWidget


class ColorButton(QPushButton):
    """A swatch that opens a colour picker and reports the chosen RGB value."""

    color_changed = Signal(object)

    def __init__(
        self,
        color: tuple[int, int, int] = (255, 255, 255),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color = (int(color[0]), int(color[1]), int(color[2]))
        self.clicked.connect(self._pick)
        self._refresh()

    def color(self) -> tuple[int, int, int]:
        return self._color

    def set_color(self, color: tuple[int, int, int]) -> None:
        self._color = (int(color[0]), int(color[1]), int(color[2]))
        self._refresh()
        self.color_changed.emit(self._color)

    def _pick(self) -> None:
        selected = QColorDialog.getColor(QColor(*self._color), self, "Border colour")
        if selected.isValid():
            self.set_color((selected.red(), selected.green(), selected.blue()))

    def _refresh(self) -> None:
        red, green, blue = self._color
        self.setText(f"#{red:02x}{green:02x}{blue:02x}")
        brightness = (red * 299 + green * 587 + blue * 114) // 1000
        text = "black" if brightness > 140 else "white"
        self.setStyleSheet(f"background-color: rgb({red}, {green}, {blue}); color: {text};")
