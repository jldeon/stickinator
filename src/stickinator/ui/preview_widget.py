"""Image preview: aspect-fit scaling over a checkerboard, no zoom or pan."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPixmap,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

CHECKERBOARD_SIZE = 10
CHECKERBOARD_LIGHT = QColor(255, 255, 255)
CHECKERBOARD_DARK = QColor(204, 204, 204)

MINIMUM_WIDTH = 320
MINIMUM_HEIGHT = 240


def to_qimage(image: np.ndarray) -> QImage:
    """Copy an RGBA8 array into a QImage the widget owns."""
    height, width, channels = image.shape
    if channels != 4:
        msg = "preview expects an (H, W, 4) array"
        raise ValueError(msg)

    contiguous = np.ascontiguousarray(image)
    view = QImage(
        contiguous.data,
        width,
        height,
        int(contiguous.strides[0]),
        QImage.Format.Format_RGBA8888,
    )
    return view.copy()


class PreviewWidget(QWidget):
    """Draws the document scaled to fit, keeping its aspect ratio."""

    picked = Signal(int, int, object)
    pick_cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self._source_size = QSize()
        self._scaled: QImage | None = None
        self._scaled_size = QSize()
        self._checkerboard = _make_checkerboard()
        self._picking = False

        self.setObjectName("previewWidget")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(MINIMUM_WIDTH, MINIMUM_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_image(self, image: np.ndarray) -> None:
        self._image = to_qimage(image)
        self._source_size = self._image.size()
        self._scaled = None
        self._scaled_size = QSize()
        self.update()

    def clear(self) -> None:
        self._image = None
        self._source_size = QSize()
        self._scaled = None
        self._scaled_size = QSize()
        self.update()

    @property
    def has_image(self) -> bool:
        return self._image is not None

    @property
    def picking(self) -> bool:
        return self._picking

    def begin_pick(self) -> None:
        """Turn the next left click into an eyedropper sample."""
        if self._image is None:
            return
        self._picking = True
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def end_pick(self) -> None:
        self._picking = False
        self.unsetCursor()

    def image_point(self, point: QPoint) -> tuple[int, int] | None:
        """Map a widget coordinate to an image pixel, or None when outside."""
        if self._image is None:
            return None

        rect = self.image_rect()
        if rect.isNull() or not rect.contains(point):
            return None

        x = int((point.x() - rect.x()) * self._source_size.width() / rect.width())
        y = int((point.y() - rect.y()) * self._source_size.height() / rect.height())
        x = min(max(x, 0), self._source_size.width() - 1)
        y = min(max(y, 0), self._source_size.height() - 1)
        return x, y

    def colour_at(self, x: int, y: int) -> tuple[int, int, int]:
        assert self._image is not None
        colour = self._image.pixelColor(x, y)
        return (colour.red(), colour.green(), colour.blue())

    def image_rect(self) -> QRect:
        """Where the image is drawn in widget coordinates."""
        if self._image is None:
            return QRect()

        scaled = self._source_size.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        return QRect(x, y, scaled.width(), scaled.height())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self._picking:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.RightButton:
            self.end_pick()
            self.pick_cancelled.emit()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        point = self.image_point(event.position().toPoint())
        if point is None:
            return

        x, y = point
        colour = self.colour_at(x, y)
        self.end_pick()
        self.picked.emit(x, y, colour)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._picking and event.key() == Qt.Key.Key_Escape:
            self.end_pick()
            self.pick_cancelled.emit()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())

        if self._image is None:
            painter.setPen(self.palette().placeholderText().color())
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Open an image to begin")
            return

        target = self.image_rect()
        painter.fillRect(target, self._checkerboard)

        if self._scaled is None or self._scaled_size != target.size():
            self._scaled = self._image.scaled(
                target.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._scaled_size = target.size()

        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(target.topLeft(), self._scaled)


def _make_checkerboard() -> QBrush:
    tile = QPixmap(CHECKERBOARD_SIZE * 2, CHECKERBOARD_SIZE * 2)
    tile.fill(CHECKERBOARD_LIGHT)

    painter = QPainter(tile)
    painter.fillRect(0, 0, CHECKERBOARD_SIZE, CHECKERBOARD_SIZE, CHECKERBOARD_DARK)
    painter.fillRect(
        CHECKERBOARD_SIZE,
        CHECKERBOARD_SIZE,
        CHECKERBOARD_SIZE,
        CHECKERBOARD_SIZE,
        CHECKERBOARD_DARK,
    )
    painter.end()

    return QBrush(tile)
