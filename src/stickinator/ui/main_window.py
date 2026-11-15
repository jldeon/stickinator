"""Main window: preview, button column, file actions and unsaved-change guards."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QMimeData, QSize, Qt
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from stickinator import APP_NAME
from stickinator.core.image_doc import Document
from stickinator.core.io import ImageLoadError, ImageSaveError, RGBAImage, save_png
from stickinator.core.settings import Settings
from stickinator.ui.preview_widget import PreviewWidget

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
    ) -> None:
        super().__init__(parent)
        self._settings = settings or Settings()
        self._document: Document | None = None
        self._save_path: Path | None = None
        self._original_source: Path | None = None

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
        for button in self._operation_buttons:
            # Wired up in the milestones that implement each operation.
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

        for widget in (self._save_button, self._save_action, self._save_as_action):
            widget.setEnabled(has_document)
        self._undo_button.setEnabled(can_undo)
        self._undo_action.setEnabled(can_undo)

        # Operation buttons stay disabled until the milestone that wires them.
        for button in self._operation_buttons:
            button.setEnabled(False)

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
