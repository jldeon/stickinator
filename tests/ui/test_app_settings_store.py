"""Application settings storage: general defaults and the AI settings block."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from stickinator.core.ai.config import AiSettings, OpenAIConfig
from stickinator.core.settings import DEFAULT_DPI, Settings
from stickinator.ui.settings_store import AppSettingsStore

MEGABYTE = 1024 * 1024


@pytest.fixture
def qsettings(tmp_path: Path) -> QSettings:
    store = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    store.clear()
    return store


@pytest.fixture
def store(qsettings: QSettings) -> AppSettingsStore:
    return AppSettingsStore(qsettings)


def test_general_round_trips(store: AppSettingsStore) -> None:
    expected = Settings(default_dpi=150.0, undo_memory_limit_bytes=64 * MEGABYTE)

    store.save_general(expected)

    assert store.load_general() == expected


def test_general_falls_back_on_bad_values(qsettings: QSettings, store: AppSettingsStore) -> None:
    qsettings.setValue("general/default_dpi", "not a number")
    qsettings.setValue("general/undo_memory_limit_bytes", -5)

    loaded = store.load_general()

    assert loaded.default_dpi == DEFAULT_DPI
    assert loaded.undo_memory_limit_bytes == Settings().undo_memory_limit_bytes


def test_ai_settings_round_trip(store: AppSettingsStore) -> None:
    expected = AiSettings(
        provider="openai",
        timeout=33.0,
        local_model="birefnet-general",
        local_alpha_matting=True,
        http_url="https://remove.example/api",
        http_extra_headers="X-Trace: 1",
        openai_model="gpt-image-1",
        openai_prompt="cut it out",
    )

    store.save_ai(expected)

    assert store.load_ai() == expected


def test_ai_settings_default_when_absent(store: AppSettingsStore) -> None:
    assert store.load_ai() == AiSettings()


def test_to_context_maps_every_provider() -> None:
    settings = AiSettings(
        provider="http",
        timeout=9.0,
        local_model="u2net",
        local_coreml=True,
        local_model_dir="/models",
        http_url="https://x",
        http_field="file",
        http_auth_header="Authorization",
        http_auth_format="Bearer {key}",
        http_extra_fields="size: auto",
        openai_base_url="https://openai.example/v1",
        openai_model="gpt-image-2",
        openai_prompt="remove",
    )

    context = settings.to_context("secret")

    assert context.provider == "http"
    assert context.api_key == "secret"
    assert context.timeout == 9.0
    assert context.local.model == "u2net"
    assert context.local.use_coreml is True
    assert context.local.model_dir == "/models"
    assert context.http.field_name == "file"
    assert context.http.auth_header == "Authorization"
    assert context.openai.base_url == "https://openai.example/v1"
    assert context.openai.model == "gpt-image-2"
    assert isinstance(context.openai, OpenAIConfig)
