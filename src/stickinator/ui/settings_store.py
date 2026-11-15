"""Persist operation parameters in QSettings as versioned JSON."""

from __future__ import annotations

import dataclasses
import json
from typing import Any, TypeVar

from PySide6.QtCore import QSettings

from stickinator.core.ai.config import AiSettings
from stickinator.core.ops.base import Params
from stickinator.core.settings import (
    DEFAULT_DPI,
    DEFAULT_UNDO_MEMORY_LIMIT_BYTES,
    Settings,
)

PARAMS_VERSION = 1
PARAMS_GROUP = "operations"
GENERAL_GROUP = "general"
AI_SETTINGS_KEY = "ai.settings"

P = TypeVar("P", bound=Params)


class ParamsStore:
    """Remembers the last values used for each operation."""

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings if settings is not None else QSettings()

    def load(self, key: str, defaults: P) -> P:
        """Return saved params, falling back to ``defaults`` on any mismatch."""
        raw = self._settings.value(self._storage_key(key))
        if not isinstance(raw, str):
            return defaults

        try:
            document = json.loads(raw)
        except (TypeError, ValueError):
            return defaults
        if not isinstance(document, dict) or document.get("version") != PARAMS_VERSION:
            return defaults

        values = document.get("values")
        if not isinstance(values, dict):
            return defaults

        defaults_by_name = {field.name: field for field in dataclasses.fields(defaults)}
        collected: dict[str, Any] = {}
        for name, field in defaults_by_name.items():
            if name not in values:
                continue
            if field.default is dataclasses.MISSING:
                return defaults
            try:
                collected[name] = _coerce(field.default, values[name])
            except (TypeError, ValueError):
                return defaults

        try:
            return type(defaults)(**collected)
        except (TypeError, ValueError):
            return defaults

    def save(self, key: str, params: Params) -> None:
        document = {
            "version": PARAMS_VERSION,
            "values": dataclasses.asdict(params),
        }
        self._settings.setValue(self._storage_key(key), json.dumps(document, sort_keys=True))
        self._settings.sync()

    @staticmethod
    def _storage_key(key: str) -> str:
        return f"{PARAMS_GROUP}/{key}"


def _coerce(expected: Any, value: Any) -> Any:
    """Convert JSON lists back into tuple fields, and guard scalar types."""
    if isinstance(expected, tuple):
        if not isinstance(value, list | tuple) or len(value) != len(expected):
            msg = "wrong tuple shape"
            raise ValueError(msg)
        return tuple(_coerce(item, element) for item, element in zip(expected, value, strict=True))

    if isinstance(expected, bool):
        if not isinstance(value, bool):
            msg = "expected a boolean"
            raise ValueError(msg)
        return value
    if isinstance(expected, int):
        if isinstance(value, bool):
            msg = "expected an integer"
            raise ValueError(msg)
        return int(value)
    if isinstance(expected, float):
        return float(value)
    if isinstance(expected, str):
        if not isinstance(value, str):
            msg = "expected a string"
            raise ValueError(msg)
        return value
    return value


class AppSettingsStore:
    """General application settings plus the flat AI settings block."""

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings if settings is not None else QSettings()
        self._params = ParamsStore(self._settings)

    def load_general(self) -> Settings:
        dpi = _read_float(self._settings.value(f"{GENERAL_GROUP}/default_dpi"), DEFAULT_DPI)
        limit = _read_int(
            self._settings.value(f"{GENERAL_GROUP}/undo_memory_limit_bytes"),
            DEFAULT_UNDO_MEMORY_LIMIT_BYTES,
        )
        try:
            return Settings(default_dpi=dpi, undo_memory_limit_bytes=limit)
        except ValueError:
            return Settings()

    def save_general(self, settings: Settings) -> None:
        self._settings.setValue(f"{GENERAL_GROUP}/default_dpi", settings.default_dpi)
        self._settings.setValue(
            f"{GENERAL_GROUP}/undo_memory_limit_bytes",
            settings.undo_memory_limit_bytes,
        )
        self._settings.sync()

    def load_ai(self) -> AiSettings:
        return self._params.load(AI_SETTINGS_KEY, AiSettings())

    def save_ai(self, settings: AiSettings) -> None:
        self._params.save(AI_SETTINGS_KEY, settings)


def _read_float(raw: object, fallback: float) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float | str):
        return fallback
    try:
        return float(raw)
    except (TypeError, ValueError):
        return fallback


def _read_int(raw: object, fallback: int) -> int:
    if isinstance(raw, bool):
        return fallback
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    if isinstance(raw, str):
        try:
            return int(raw)
        except ValueError:
            return fallback
    return fallback
