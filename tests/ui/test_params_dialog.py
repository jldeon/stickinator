"""Params dialog shell: population, reset and collection."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QSpinBox
from pytestqt.qtbot import QtBot

from stickinator.core.ops.base import Params
from stickinator.ui.dialogs.base import ParamsDialog


@dataclass(frozen=True, slots=True)
class _SampleParams(Params):
    value: int = 5


class _SampleDialog(ParamsDialog[_SampleParams]):
    def build_form(self) -> None:
        self._spin = QSpinBox()
        self._spin.setRange(0, 100)
        self._form.addRow("Value", self._spin)

    def set_params(self, params: _SampleParams) -> None:
        self._spin.setValue(params.value)

    def params(self) -> _SampleParams:
        return _SampleParams(value=self._spin.value())


def _dialog(qtbot: QtBot) -> _SampleDialog:
    dialog = _SampleDialog("Sample", _SampleParams(value=12), _SampleParams(value=5))
    qtbot.addWidget(dialog)
    return dialog


def test_starts_with_the_supplied_values(qtbot: QtBot) -> None:
    dialog = _dialog(qtbot)

    assert dialog.params() == _SampleParams(value=12)


def test_reset_restores_defaults(qtbot: QtBot) -> None:
    dialog = _dialog(qtbot)
    dialog._spin.setValue(40)

    dialog.reset()

    assert dialog.params() == _SampleParams(value=5)


def test_accept_collects_the_values(qtbot: QtBot) -> None:
    dialog = _dialog(qtbot)
    dialog._spin.setValue(40)

    dialog.accept()

    assert dialog.accepted_params() == _SampleParams(value=40)


def test_accepted_params_is_empty_until_accept(qtbot: QtBot) -> None:
    dialog = _dialog(qtbot)

    assert dialog.accepted_params() is None
