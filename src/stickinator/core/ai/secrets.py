"""Keychain access for provider keys.

Keys are never written to QSettings or logs. When the platform keyring is
unavailable the caller gets an empty string and can keep a key in memory for the
session instead.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SERVICE = "stickinator"


def _keyring():  # type: ignore[no-untyped-def]
    """Indirection so tests can substitute a fake keyring."""
    import keyring

    return keyring


def key_name(provider: str) -> str:
    return f"{provider}-api-key"


def get_api_key(provider: str) -> str:
    try:
        value = _keyring().get_password(SERVICE, key_name(provider))
    except Exception as exc:
        logger.warning("Could not read the %s key from the keychain: %s", provider, exc)
        return ""
    return value or ""


def set_api_key(provider: str, value: str) -> bool:
    """Store or delete a key. Returns False when the keychain is unavailable."""
    try:
        if value:
            _keyring().set_password(SERVICE, key_name(provider), value)
        else:
            try:
                _keyring().delete_password(SERVICE, key_name(provider))
            except Exception:
                return True
    except Exception as exc:
        logger.warning("Could not write the %s key to the keychain: %s", provider, exc)
        return False
    return True
