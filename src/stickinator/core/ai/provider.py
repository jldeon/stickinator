"""Errors raised by AI background-removal providers."""

from __future__ import annotations


class ProviderError(Exception):
    """A provider could not produce a cutout; the message is user-facing."""
