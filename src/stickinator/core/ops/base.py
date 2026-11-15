"""Operation contracts shared by the core and the UI.

Parameters are plain dataclasses with JSON-friendly fields. Never put Qt types
in here: operations run in a child process and their parameters are pickled.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

RGBAImage = NDArray[np.uint8]


class OperationCancelled(Exception):
    """Raised by an operation once the user has cancelled it."""


class CancelToken(Protocol):
    """Cooperative cancellation, checked between steps inside an operation."""

    @property
    def cancelled(self) -> bool: ...

    def raise_if_cancelled(self) -> None: ...


class NeverCancelled:
    """Cancel token for direct calls and tests."""

    @property
    def cancelled(self) -> bool:
        return False

    def raise_if_cancelled(self) -> None:
        return


@dataclass(frozen=True, slots=True)
class Params:
    """Base class for per-operation parameters.

    Subclasses must be frozen dataclasses whose fields are bool, int, float,
    str, or tuples of numbers.
    """


@dataclass(frozen=True, slots=True)
class Operation[P: Params]:
    """A named image operation plus the parameters it expects."""

    key: str
    label: str
    params_type: type[P]
    run: Callable[[RGBAImage, P, CancelToken], RGBAImage]


def defaults_of[P: Params](params_type: type[P]) -> P:
    """Build the all-defaults instance of a params dataclass."""
    return params_type()
