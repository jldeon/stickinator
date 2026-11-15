"""Preview widget: conversion, aspect fitting and painting."""

from __future__ import annotations

import numpy as np
from pytestqt.qtbot import QtBot

from stickinator.ui.preview_widget import PreviewWidget, to_qimage


def _image(width: int = 100, height: int = 50) -> np.ndarray:
    image = np.zeros((height, width, 4), dtype=np.uint8)
    image[..., 0] = 200
    image[..., 3] = 255
    image[0, 0] = (10, 20, 30, 255)
    return image


def test_to_qimage_keeps_pixels_and_alpha() -> None:
    qimage = to_qimage(_image(2, 2))

    assert qimage.size().width() == 2
    assert qimage.size().height() == 2
    colour = qimage.pixelColor(0, 0)
    assert (colour.red(), colour.green(), colour.blue(), colour.alpha()) == (
        10,
        20,
        30,
        255,
    )


def test_image_rect_keeps_the_aspect_ratio(qtbot: QtBot) -> None:
    widget = PreviewWidget()
    qtbot.addWidget(widget)
    widget.resize(400, 400)

    widget.set_image(_image(100, 50))

    rect = widget.image_rect()
    assert rect.width() == 400
    assert rect.height() == 200
    assert rect.left() == 0
    assert rect.top() == 100


def test_clear_removes_the_image(qtbot: QtBot) -> None:
    widget = PreviewWidget()
    qtbot.addWidget(widget)
    widget.set_image(_image())

    widget.clear()

    assert not widget.has_image
    assert widget.image_rect().isNull()


def test_paints_without_an_image(qtbot: QtBot) -> None:
    widget = PreviewWidget()
    qtbot.addWidget(widget)
    widget.resize(400, 300)

    pixmap = widget.grab()

    assert not pixmap.isNull()
