"""Settings dialog: AI providers, keychain keys and general defaults."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from stickinator.core.ai.config import (
    DEFAULT_OPENAI_PROMPT,
    HTTP,
    LOCAL,
    OPENAI,
    AiSettings,
)
from stickinator.core.ai.local_rembg import MODELS
from stickinator.core.ai.secrets import get_api_key, set_api_key
from stickinator.core.settings import Settings
from stickinator.ui.settings_store import AppSettingsStore

MEGABYTE = 1024 * 1024
PANEL_MIN_WIDTH = 380


class SettingsDialog(QDialog):
    def __init__(self, store: AppSettingsStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._general = store.load_general()
        self._ai = store.load_ai()
        self._stored_keys = {
            HTTP: get_api_key(HTTP),
            OPENAI: get_api_key(OPENAI),
        }

        self.setWindowTitle("Settings")
        self.setModal(True)

        tabs = QTabWidget(self)
        tabs.addTab(self._build_ai_tab(), "AI")
        tabs.addTab(self._build_general_tab(), "General")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------- build

    def _build_ai_tab(self) -> QWidget:
        tab = QWidget(self)
        columns = QHBoxLayout(tab)

        behaviour = QGroupBox("Default provider")
        behaviour_form = QFormLayout(behaviour)
        self._provider = QComboBox()
        self._provider.setObjectName("providerCombo")
        for label, value in (
            ("Local (rembg)", LOCAL),
            ("Generic HTTP endpoint", HTTP),
            ("OpenAI-compatible edits", OPENAI),
        ):
            self._provider.addItem(label, value)
        index = self._provider.findData(self._ai.provider)
        if index >= 0:
            self._provider.setCurrentIndex(index)

        self._timeout = _double_spin(1.0, 3600.0)
        self._timeout.setSuffix(" s")
        self._timeout.setValue(self._ai.timeout)
        self._timeout.setObjectName("timeoutSpin")

        behaviour_form.addRow("Provider", self._provider)
        behaviour_form.addRow("Request timeout", self._timeout)

        local = QGroupBox("Local (rembg)")
        local_form = QFormLayout(local)
        self._local_model = QComboBox()
        self._local_model.setObjectName("localModelCombo")
        for model in MODELS:
            self._local_model.addItem(model, model)
        index = self._local_model.findData(self._ai.local_model)
        if index >= 0:
            self._local_model.setCurrentIndex(index)

        self._alpha_matting = QCheckBox("Alpha matting")
        self._alpha_matting.setObjectName("alphaMattingCheck")
        self._alpha_matting.setChecked(self._ai.local_alpha_matting)

        self._foreground = _int_spin(0, 255)
        self._foreground.setValue(self._ai.local_foreground)
        self._foreground.setObjectName("foregroundSpin")
        self._background = _int_spin(0, 255)
        self._background.setValue(self._ai.local_background)
        self._background.setObjectName("backgroundSpin")
        self._erode = _int_spin(0, 100)
        self._erode.setValue(self._ai.local_erode)
        self._erode.setObjectName("erodeSpin")

        self._coreml = QCheckBox("Use CoreML when available")
        self._coreml.setObjectName("coremlCheck")
        self._coreml.setChecked(self._ai.local_coreml)

        self._model_dir = QLineEdit(self._ai.local_model_dir)
        self._model_dir.setObjectName("modelDirEdit")
        self._model_dir.setPlaceholderText("Default: ~/.u2net")

        local_form.addRow("Model", self._local_model)
        local_form.addRow("", self._alpha_matting)
        local_form.addRow("Foreground threshold", self._foreground)
        local_form.addRow("Background threshold", self._background)
        local_form.addRow("Erode size", self._erode)
        local_form.addRow("", self._coreml)
        local_form.addRow("Model folder", self._model_dir)

        remote = QGroupBox("Generic HTTP endpoint")
        remote_form = QFormLayout(remote)
        self._http_url = QLineEdit(self._ai.http_url)
        self._http_url.setObjectName("httpUrlEdit")
        self._http_field = QLineEdit(self._ai.http_field)
        self._http_field.setObjectName("httpFieldEdit")
        self._http_header = QLineEdit(self._ai.http_auth_header)
        self._http_header.setObjectName("httpHeaderEdit")
        self._http_format = QLineEdit(self._ai.http_auth_format)
        self._http_format.setObjectName("httpFormatEdit")
        self._http_headers = QLineEdit(self._ai.http_extra_headers)
        self._http_headers.setObjectName("httpHeadersEdit")
        self._http_fields = QLineEdit(self._ai.http_extra_fields)
        self._http_fields.setObjectName("httpFieldsEdit")
        self._http_key = _key_field(self._stored_keys[HTTP], "httpKeyEdit")

        remote_form.addRow("URL", self._http_url)
        remote_form.addRow("Image field", self._http_field)
        remote_form.addRow("Auth header", self._http_header)
        remote_form.addRow("Auth format", self._http_format)
        remote_form.addRow("Extra headers", self._http_headers)
        remote_form.addRow("Extra fields", self._http_fields)
        remote_form.addRow("API key", self._http_key)

        openai = QGroupBox("OpenAI-compatible edits")
        openai_form = QFormLayout(openai)
        self._openai_url = QLineEdit(self._ai.openai_base_url)
        self._openai_url.setObjectName("openaiUrlEdit")
        self._openai_model = QLineEdit(self._ai.openai_model)
        self._openai_model.setObjectName("openaiModelEdit")
        self._openai_prompt = QLineEdit(self._ai.openai_prompt)
        self._openai_prompt.setObjectName("openaiPromptEdit")
        self._openai_key = _key_field(self._stored_keys[OPENAI], "openaiKeyEdit")

        openai_form.addRow("Base URL", self._openai_url)
        openai_form.addRow("Model", self._openai_model)
        openai_form.addRow("Prompt", self._openai_prompt)
        openai_form.addRow("API key", self._openai_key)

        # Two columns keep the dialog within the height of a laptop screen:
        # local settings on the left, remote providers on the right. Equal
        # minimum widths keep the two columns balanced when the dialog grows.
        for panel in (behaviour, local, remote, openai):
            panel.setMinimumWidth(PANEL_MIN_WIDTH)

        left = QVBoxLayout()
        left.addWidget(behaviour)
        left.addWidget(local)
        left.addStretch(1)

        right = QVBoxLayout()
        right.addWidget(remote)
        right.addWidget(openai)
        right.addStretch(1)

        columns.addLayout(left, 1)
        columns.addLayout(right, 1)
        return tab

    def _build_general_tab(self) -> QWidget:
        tab = QWidget(self)
        form = QFormLayout(tab)
        # The AI tab makes the dialog wide; keep the few general fields compact.
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)

        self._default_dpi = _double_spin(1.0, 5000.0)
        self._default_dpi.setSuffix(" dpi")
        self._default_dpi.setValue(self._general.default_dpi)
        self._default_dpi.setMinimumWidth(180)
        self._default_dpi.setObjectName("defaultDpiSpin")

        self._undo_megabytes = _int_spin(0, 100_000)
        self._undo_megabytes.setSuffix(" MB")
        self._undo_megabytes.setValue(self._general.undo_memory_limit_bytes // MEGABYTE)
        self._undo_megabytes.setMinimumWidth(180)
        self._undo_megabytes.setObjectName("undoLimitSpin")

        form.addRow("Default DPI", self._default_dpi)
        form.addRow("Undo memory limit", self._undo_megabytes)
        form.addRow("", QLabel("API keys are stored in the macOS Keychain."))
        return tab

    # ---------------------------------------------------------------- actions

    def _collect_ai(self) -> AiSettings:
        return AiSettings(
            provider=self._provider.currentData(),
            timeout=self._timeout.value(),
            local_model=self._local_model.currentData(),
            local_alpha_matting=self._alpha_matting.isChecked(),
            local_foreground=self._foreground.value(),
            local_background=self._background.value(),
            local_erode=self._erode.value(),
            local_coreml=self._coreml.isChecked(),
            local_model_dir=self._model_dir.text().strip(),
            http_url=self._http_url.text().strip(),
            http_field=self._http_field.text().strip() or "image",
            http_auth_header=self._http_header.text().strip(),
            http_auth_format=self._http_format.text().strip() or "{key}",
            http_extra_headers=self._http_headers.text().strip(),
            http_extra_fields=self._http_fields.text().strip(),
            openai_base_url=self._openai_url.text().strip() or "https://api.openai.com/v1",
            openai_model=self._openai_model.text().strip() or "gpt-image-1",
            openai_prompt=self._openai_prompt.text().strip() or DEFAULT_OPENAI_PROMPT,
        )

    def _collect_general(self) -> Settings:
        return Settings(
            default_dpi=self._default_dpi.value(),
            undo_memory_limit_bytes=self._undo_megabytes.value() * MEGABYTE,
        )

    def accept(self) -> None:
        try:
            ai = self._collect_ai()
            general = self._collect_general()
        except ValueError as exc:
            self._warn("Settings", str(exc))
            return

        self._store.save_ai(ai)
        self._store.save_general(general)

        unavailable: list[str] = []
        for provider, field in ((HTTP, self._http_key), (OPENAI, self._openai_key)):
            if field.text() == self._stored_keys.get(provider, ""):
                continue
            if not set_api_key(provider, field.text()):
                unavailable.append(provider)
        if unavailable:
            self._warn(
                "Keychain unavailable",
                "The key could not be stored in the system keychain. It will be "
                "kept for this session only.",
            )
        super().accept()

    def _warn(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)


def _double_spin(minimum: float, maximum: float) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(2)
    return box


def _int_spin(minimum: int, maximum: int) -> QSpinBox:
    box = QSpinBox()
    box.setRange(minimum, maximum)
    return box


def _key_field(value: str, name: str) -> QLineEdit:
    field = QLineEdit(value)
    field.setEchoMode(QLineEdit.EchoMode.Password)
    field.setObjectName(name)
    field.setPlaceholderText("Stored in the system keychain")
    return field
