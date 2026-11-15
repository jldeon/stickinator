"""Shared shell for per-operation parameter dialogs."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from stickinator.core.ops.base import Params


class ParamsDialog[P: Params](QDialog):
    """Modal form with Reset to defaults, OK and Cancel.

    Subclasses build widgets in :meth:`build_form`, then map them in
    :meth:`set_params` and :meth:`params`. Call :meth:`accepted_params` after
    ``exec()`` to fetch the values.
    """

    def __init__(
        self,
        title: str,
        params: P,
        defaults: P,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._defaults = defaults
        self._accepted_params: P | None = None

        self.setWindowTitle(title)
        self.setModal(True)

        self._form = QFormLayout()
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        reset_button = self._buttons.addButton(
            "Reset to defaults", QDialogButtonBox.ButtonRole.ResetRole
        )
        reset_button.clicked.connect(self.reset)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(self._form)
        layout.addWidget(self._buttons)

        self.build_form()
        self.set_params(params)

    def build_form(self) -> None:
        """Create widgets and add rows to ``self._form``."""
        raise NotImplementedError

    def set_params(self, params: P) -> None:
        """Push values into the widgets."""
        raise NotImplementedError

    def params(self) -> P:
        """Collect a params instance from the widgets."""
        raise NotImplementedError

    def validate(self, params: P) -> str | None:
        """Return an error message to block acceptance, or None."""
        return None

    def reset(self) -> None:
        self.set_params(self._defaults)

    def accept(self) -> None:
        params = self.params()
        error = self.validate(params)
        if error:
            QMessageBox.warning(self, self.windowTitle(), error)
            return
        self._accepted_params = params
        super().accept()

    def accepted_params(self) -> P | None:
        return self._accepted_params
