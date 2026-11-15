"""Keychain helpers: storing, clearing and surviving a missing backend."""

from __future__ import annotations

import pytest

from stickinator.core.ai import secrets


class FakeKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, name: str) -> str | None:
        return self.values.get((service, name))

    def set_password(self, service: str, name: str, value: str) -> None:
        self.values[(service, name)] = value

    def delete_password(self, service: str, name: str) -> None:
        del self.values[(service, name)]


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeKeyring:
    backend = FakeKeyring()
    monkeypatch.setattr(secrets, "_keyring", lambda: backend)
    return backend


def test_round_trips_a_key(fake: FakeKeyring) -> None:
    assert secrets.set_api_key("openai", "secret")
    assert secrets.get_api_key("openai") == "secret"
    assert fake.values[(secrets.SERVICE, "openai-api-key")] == "secret"


def test_empty_value_deletes_the_key(fake: FakeKeyring) -> None:
    secrets.set_api_key("http", "secret")

    assert secrets.set_api_key("http", "")
    assert secrets.get_api_key("http") == ""


def test_deleting_a_missing_key_is_fine(fake: FakeKeyring) -> None:
    assert secrets.set_api_key("local", "")


def test_missing_backend_reads_as_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> None:
        raise RuntimeError("no keychain")

    monkeypatch.setattr(secrets, "_keyring", broken)

    assert secrets.get_api_key("openai") == ""


def test_missing_backend_reports_a_failed_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken() -> None:
        raise RuntimeError("no keychain")

    monkeypatch.setattr(secrets, "_keyring", broken)

    assert not secrets.set_api_key("openai", "secret")
