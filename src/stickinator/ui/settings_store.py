"""Persist operation parameters in QSettings as versioned JSON."""

from __future__ import annotations

import dataclasses
import json
from typing import Any, TypeVar

from PySide6.QtCore import QSettings

from stickinator.core.ops.base import Params

PARAMS_VERSION = 1
PARAMS_GROUP = "operations"

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
