"""Params persistence: round-trips, fallbacks and schema versioning."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from tests.helpers.fake_ops import FakeParams

from stickinator.ui.settings_store import PARAMS_VERSION, ParamsStore

KEY = "fake.fill"


@pytest.fixture
def settings(tmp_path: Path) -> QSettings:
    store = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    store.clear()
    return store


@pytest.fixture
def store(settings: QSettings) -> ParamsStore:
    return ParamsStore(settings)


def test_round_trips_all_field_types(store: ParamsStore) -> None:
    params = FakeParams(value=7, delay=1.5, color=(1, 2, 3), enabled=False)

    store.save(KEY, params)

    assert store.load(KEY, FakeParams()) == params


def test_missing_entry_returns_defaults(store: ParamsStore) -> None:
    assert store.load(KEY, FakeParams(value=9)) == FakeParams(value=9)


def test_corrupt_json_returns_defaults(settings: QSettings, store: ParamsStore) -> None:
    settings.setValue(f"operations/{KEY}", "{not json")

    assert store.load(KEY, FakeParams(value=9)) == FakeParams(value=9)


def test_version_mismatch_returns_defaults(settings: QSettings, store: ParamsStore) -> None:
    payload = {"version": PARAMS_VERSION + 1, "values": {"value": 3}}
    settings.setValue(f"operations/{KEY}", json.dumps(payload))

    assert store.load(KEY, FakeParams(value=9)) == FakeParams(value=9)


def test_unknown_fields_are_ignored(settings: QSettings, store: ParamsStore) -> None:
    payload = {
        "version": PARAMS_VERSION,
        "values": {"value": 3, "from_a_newer_build": True},
    }
    settings.setValue(f"operations/{KEY}", json.dumps(payload))

    assert store.load(KEY, FakeParams()).value == 3


def test_wrong_scalar_type_returns_defaults(settings: QSettings, store: ParamsStore) -> None:
    payload = {"version": PARAMS_VERSION, "values": {"value": "three"}}
    settings.setValue(f"operations/{KEY}", json.dumps(payload))

    assert store.load(KEY, FakeParams(value=9)) == FakeParams(value=9)


def test_wrong_tuple_shape_returns_defaults(settings: QSettings, store: ParamsStore) -> None:
    payload = {"version": PARAMS_VERSION, "values": {"color": [1, 2]}}
    settings.setValue(f"operations/{KEY}", json.dumps(payload))

    assert store.load(KEY, FakeParams(color=(9, 9, 9))) == FakeParams(color=(9, 9, 9))
