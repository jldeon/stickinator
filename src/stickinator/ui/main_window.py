"""Main window: preview, button column, file actions and unsaved-change guards."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum, auto
from functools import partial
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QEventLoop, QMimeData, QSize, Qt
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from stickinator import APP_NAME
from stickinator.core.image_doc import Document
from stickinator.core.io import ImageLoadError, ImageSaveError, RGBAImage, save_png
from stickinator.core.ops.base import (
    Operation,
    OperationContext,
    OperationResult,
    Params,
)
from stickinator.core.ops.bg_algorithmic import BG_REMOVAL
from stickinator.core.ops.border import BORDER
from stickinator.core.ops.extend_canvas import EXTEND_CANVAS
from stickinator.core.ops.resize import RESIZE_OPERATION
from stickinator.core.ops.trim import TRIM
from stickinator.core.settings import Settings
from stickinator.ui.dialogs.base import ParamsDialog
from stickinator.ui.dialogs.bg_algorithmic import ChromaKeyDialog, Sample
from stickinator.ui.dialogs.border import BorderDialog
from stickinator.ui.dialogs.extend_canvas import ExtendCanvasDialog
from stickinator.ui.dialogs.resize import ResizeDialog
from stickinator.ui.dialogs.trim import TrimDialog
from stickinator.ui.preview_widget import PreviewWidget
from stickinator.ui.settings_store import ParamsStore
from stickinator.ui.worker import OperationWorker

WINDOW_SIZE = QSize(1200, 800)
BUTTON_MINIMUM_HEIGHT = 32
RIGHT_COLUMN_WIDTH = 180
SUPPORTED_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})
IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp)"
PNG_FILTER = "PNG image (*.png)"

OPERATION_BUTTONS = (
    ("Remove BG", "bgAlgorithmicButton"),
    ("Remove BG (AI)", "bgAiButton"),
    ("Extend Canvas", "extendCanvasButton"),
    ("Border", "borderButton"),
    ("Trim", "trimButton"),
    ("Resize / Print Size", "resizeButton"),
)

# Buttons wired to a real operation. The rest stay disabled until their
# milestone adds an entry here.
OPERATION_TARGETS: dict[str, tuple[Operation[Any], type[ParamsDialog[Any]]]] = {
    "bgAlgorithmicButton": (BG_REMOVAL, ChromaKeyDialog),
    "extendCanvasButton": (EXTEND_CANVAS, ExtendCanvasDialog),
    "borderButton": (BORDER, BorderDialog),
    "trimButton": (TRIM, TrimDialog),
    "resizeButton": (RESIZE_OPERATION, ResizeDialog),
}


class UnsavedChoice(Enum):
    """What the user chose when asked about unsaved changes."""

    SAVE = auto()
    DISCARD = auto()
    CANCEL = auto()


class MainWindow(QMainWindow):
    """The single application window."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        settings: Settings | None = None,
        params_store: ParamsStore | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings or Settings()
        self._params_store = params_store if params_store is not None else ParamsStore()
        self._document: Document | None = None
        self._save_path: Path | None = None
        self._original_source: Path | None = None
        self._busy = False
        self._progress: QProgressDialog | None = None

        self._worker = OperationWorker(self)
        self._worker.finished.connect(self._on_operation_finished)
        self._worker.failed.connect(self._on_operation_failed)
        self._worker.cancelled.connect(self._on_operation_cancelled)

        self.setWindowTitle(APP_NAME)
        self.resize(WINDOW_SIZE)
        self.setAcceptDrops(True)

        self._build_ui()
        self._build_menus()
        self._update_actions()

    # ------------------------------------------------------------------ state

    @property
    def document(self) -> Document | None:
        return self._document

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def worker(self) -> OperationWorker:
        return self._worker

    # --------------------------------------------------------------------- ui

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        preview_column = QVBoxLayout()
        preview_column.setSpacing(4)
        self._preview = PreviewWidget(central)
        self._status = QLabel("No image loaded", central)
        self._status.setObjectName("statusLabel")
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        preview_column.addWidget(self._preview, 1)
        preview_column.addWidget(self._status)
        layout.addLayout(preview_column, 1)

        button_column = QVBoxLayout()
        button_column.setSpacing(6)

        self._open_button = self._make_button("Open", "openButton", self.open_file)
        self._operation_buttons = [
            self._make_button(label, name, None) for label, name in OPERATION_BUTTONS
        ]
        self._undo_button = self._make_button("Undo", "undoButton", self.undo)
        self._save_button = self._make_button("Save", "saveButton", self.save)

        button_column.addWidget(self._open_button)
        button_column.addSpacing(8)
        for (_, name), button in zip(OPERATION_BUTTONS, self._operation_buttons, strict=True):
            if name in OPERATION_TARGETS:
                button.clicked.connect(partial(self.open_operation, name))
            button_column.addWidget(button)
        button_column.addStretch(1)
        button_column.addWidget(self._undo_button)
        button_column.addWidget(self._save_button)

        button_panel = QWidget(central)
        button_panel.setLayout(button_column)
        button_panel.setFixedWidth(RIGHT_COLUMN_WIDTH)
        layout.addWidget(button_panel)

        self.setCentralWidget(central)

    def _make_button(self, label: str, name: str, slot: Callable[[], object] | None) -> QPushButton:
        button = QPushButton(label, self)
        button.setObjectName(name)
        button.setMinimumHeight(BUTTON_MINIMUM_HEIGHT)
        if slot is not None:
            button.clicked.connect(slot)
        return button

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        self._open_action = QAction("Open…", self)
        self._open_action.setShortcut(QKeySequence.StandardKey.Open)
        self._open_action.triggered.connect(self.open_file)
        file_menu.addAction(self._open_action)

        self._save_action = QAction("Save", self)
        self._save_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_action.triggered.connect(self.save)
        file_menu.addAction(self._save_action)

        self._save_as_action = QAction("Save As…", self)
        self._save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self._save_as_action.triggered.connect(self.save_as)
        file_menu.addAction(self._save_as_action)

        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.setMenuRole(QAction.MenuRole.QuitRole)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = menu_bar.addMenu("&Edit")
        self._undo_action = QAction("Undo", self)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.triggered.connect(self.undo)
        edit_menu.addAction(self._undo_action)

    def _update_actions(self) -> None:
        document = self._document
        has_document = document is not None
        can_undo = document is not None and document.can_undo
        idle = not self._busy

        self._open_button.setEnabled(idle)
        self._open_action.setEnabled(idle)
        for widget in (self._save_button, self._save_action, self._save_as_action):
            widget.setEnabled(has_document and idle)
        self._undo_button.setEnabled(can_undo and idle)
        self._undo_action.setEnabled(can_undo and idle)

        for (_, name), button in zip(OPERATION_BUTTONS, self._operation_buttons, strict=True):
            wired = name in OPERATION_TARGETS
            button.setEnabled(has_document and idle and wired)

    def _refresh(self) -> None:
        document = self._document
        if document is None:
            self._preview.clear()
            self._status.setText("No image loaded")
            self.setWindowTitle(APP_NAME)
            self.setWindowModified(False)
        else:
            self._preview.set_image(document.image)
            self._status.setText(describe_image(document.image, document.dpi))
            name = document.source_path.name if document.source_path else "Untitled"
            self.setWindowTitle(f"{name} — {APP_NAME}[*]")
            self.setWindowModified(document.dirty)

        self._update_actions()

    # ------------------------------------------------------------- file actions

    def open_file(self) -> bool:
        """Ask for a file and open it, guarding unsaved changes first."""
        if not self._maybe_discard_changes():
            return False

        path = self._ask_open_path()
        if path is None:
            return False
        return self.load_path(path)

    def load_path(self, path: str | Path) -> bool:
        """Load a specific file, reporting decode failures to the user."""
        source = Path(path)
        try:
            document = Document.from_file(source, settings=self._settings)
        except ImageLoadError as exc:
            self._show_error("Could not open image", str(exc))
            return False

        self._document = document
        self._original_source = source
        self._save_path = None
        self._refresh()
        return True

    def save(self) -> bool:
        """Write to the current output path, asking for one the first time."""
        if self._document is None:
            return False
        if self._save_path is None:
            return self.save_as()
        return self._write(self._save_path)

    def save_as(self) -> bool:
        """Always ask for a destination."""
        document = self._document
        if document is None:
            return False

        path = self._ask_save_path(self._suggested_save_path())
        if path is None:
            return False

        original = document.source_path
        if (
            original is not None
            and path.resolve() == original.resolve()
            and not self._confirm_overwrite_original(original)
        ):
            return False

        return self._write(path)

    def undo(self) -> bool:
        """Restore the previous document state, if any."""
        document = self._document
        if document is None or not document.undo():
            return False
        self._refresh()
        return True

    # --------------------------------------------------------------- operations

    def open_operation(self, button_name: str) -> None:
        """Show the dialog for a wired operation button, then run it."""
        target = OPERATION_TARGETS.get(button_name)
        if target is None or self._document is None or self._busy:
            return

        operation, dialog_type = target
        defaults = operation.params_type()
        stored = self._params_store.load(operation.key, defaults)
        dialog = dialog_type(operation.label, stored, defaults, self)
        if isinstance(dialog, ChromaKeyDialog):
            dialog.set_colour_picker(lambda: self._pick_colour(dialog))

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        params = dialog.accepted_params()
        if params is None:
            return
        self._params_store.save(operation.key, params)
        self.start_operation(operation, params)

    def _pick_colour(self, dialog: ChromaKeyDialog) -> Sample | None:
        """Hide the dialog, let the user click the preview, then restore it."""
        if self._document is None:
            return None

        dialog.hide()
        self._preview.begin_pick()
        loop = QEventLoop()
        result: dict[str, Sample] = {}

        def on_picked(x: int, y: int, colour: object) -> None:
            result["value"] = (cast("tuple[int, int, int]", colour), (x, y))
            loop.quit()

        def on_cancelled() -> None:
            loop.quit()

        self._preview.picked.connect(on_picked)
        self._preview.pick_cancelled.connect(on_cancelled)
        loop.exec()
        self._preview.picked.disconnect(on_picked)
        self._preview.pick_cancelled.disconnect(on_cancelled)
        self._preview.end_pick()
        dialog.show()
        return result.get("value")

    def start_operation(self, operation: Operation[Any], params: Params) -> bool:
        """Run an operation in the worker against the current document."""
        document = self._document
        if document is None or self._busy:
            return False

        try:
            self._worker.start(
                operation,
                params,
                document.image,
                OperationContext(dpi=document.dpi),
            )
        except (RuntimeError, OSError) as exc:
            self._show_error("Could not start the operation", str(exc))
            return False

        self._busy = True
        self._show_progress(operation.label)
        self._update_actions()
        return True

    def _on_operation_finished(self, result: OperationResult) -> None:
        self._finish_operation()
        document = self._document
        if document is not None:
            document.apply(result.image, dpi=result.dpi)
        self._refresh()

    def _on_operation_failed(self, message: str) -> None:
        self._finish_operation()
        self._show_error("Could not finish the operation", message)
        self._refresh()

    def _on_operation_cancelled(self) -> None:
        self._finish_operation()
        self._refresh()

    def _finish_operation(self) -> None:
        self._busy = False
        self._hide_progress()

    def _show_progress(self, label: str) -> None:
        progress = QProgressDialog(f"{label}…", "Cancel", 0, 0, self)
        progress.setWindowTitle(APP_NAME)
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.canceled.connect(self._worker.cancel)
        progress.show()
        self._progress = progress

    def _hide_progress(self) -> None:
        progress = self._progress
        self._progress = None
        if progress is not None:
            progress.reset()
            progress.close()

    def _write(self, path: Path) -> bool:
        document = self._document
        if document is None:
            return False

        try:
            save_png(path, document.image, document.dpi)
        except (ImageSaveError, ValueError) as exc:
            self._show_error("Could not save", str(exc))
            return False

        document.mark_saved(path)
        self._save_path = path
        self._refresh()
        return True

    def _suggested_save_path(self) -> Path:
        if self._original_source is None:
            return Path.home() / "sticker.png"
        return self._original_source.with_name(f"{self._original_source.stem}_sticker.png")

    # ------------------------------------------------------------------ dialogs

    def _ask_open_path(self) -> Path | None:
        start = (
            str(self._original_source.parent)
            if self._original_source is not None
            else str(Path.home())
        )
        selected, _ = QFileDialog.getOpenFileName(self, "Open Image", start, IMAGE_FILTER)
        return Path(selected) if selected else None

    def _ask_save_path(self, suggested: Path) -> Path | None:
        selected, _ = QFileDialog.getSaveFileName(self, "Save Sticker", str(suggested), PNG_FILTER)
        if not selected:
            return None

        path = Path(selected)
        if path.suffix.lower() != ".png":
            path = path.with_suffix(".png")
        return path

    def _ask_unsaved_changes(self) -> UnsavedChoice:
        document = self._document
        name = (
            document.source_path.name
            if document is not None and document.source_path is not None
            else "This image"
        )

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Unsaved changes")
        box.setText(f"{name} has unsaved changes.")
        box.setInformativeText("Save your changes before continuing?")

        save_button = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        discard_button = box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_button)
        box.exec()

        clicked = box.clickedButton()
        if clicked is save_button:
            return UnsavedChoice.SAVE
        if clicked is discard_button:
            return UnsavedChoice.DISCARD
        return UnsavedChoice.CANCEL

    def _confirm_overwrite_original(self, original: Path) -> bool:
        answer = QMessageBox.question(
            self,
            "Overwrite original?",
            f"{original.name} is the file you opened. "
            "Saving will replace it with a PNG.\n\nOverwrite it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def _maybe_discard_changes(self) -> bool:
        document = self._document
        if document is None or not document.dirty:
            return True

        choice = self._ask_unsaved_changes()
        if choice is UnsavedChoice.CANCEL:
            return False
        if choice is UnsavedChoice.DISCARD:
            return True
        return self.save()

    # ------------------------------------------------------------------- events

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._dropped_path(event.mimeData()) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        path = self._dropped_path(event.mimeData())
        if path is None:
            event.ignore()
            return

        event.acceptProposedAction()
        if not self._maybe_discard_changes():
            return
        self.load_path(path)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._busy:
            self._worker.shutdown()
            self._finish_operation()

        if self._maybe_discard_changes():
            event.accept()
        else:
            event.ignore()

    def _dropped_path(self, mime: QMimeData) -> Path | None:
        if not mime.hasUrls():
            return None

        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.suffix.lower() in SUPPORTED_SUFFIXES and path.is_file():
                return path
        return None


def describe_image(image: RGBAImage, dpi: tuple[float, float]) -> str:
    """One-line summary of pixel size, resolution and print size."""
    height, width = image.shape[:2]
    x_dpi, y_dpi = dpi
    width_inches = width / x_dpi
    height_inches = height / y_dpi

    dpi_text = f"{_format_dpi(x_dpi)} DPI"
    if _format_dpi(x_dpi) != _format_dpi(y_dpi):
        dpi_text = f"{_format_dpi(x_dpi)} x {_format_dpi(y_dpi)} DPI"
    return (
        f"{width} x {height} px  |  {dpi_text}  |  "
        f"{width_inches:.2f} x {height_inches:.2f} in "
        f"({width_inches * 2.54:.2f} x {height_inches * 2.54:.2f} cm)"
    )


def _format_dpi(value: float) -> str:
    """Round-trip pHYs is never exact; one decimal of DPI is plenty."""
    text = f"{value:.1f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text
