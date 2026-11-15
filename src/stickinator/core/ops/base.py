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

from stickinator.core.ai.config import AiContext
from stickinator.core.params import Params

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
class OperationContext:
    """Document facts an operation may need but must not mutate."""

    dpi: tuple[float, float] = (300.0, 300.0)
    ai: AiContext | None = None


@dataclass(frozen=True, slots=True)
class OperationResult:
    """New pixels, plus a resolution change when the operation has one."""

    image: RGBAImage
    dpi: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class Operation[P: Params]:
    """A named image operation plus the parameters it expects."""

    key: str
    label: str
    params_type: type[P]
    run: Callable[[RGBAImage, P, OperationContext, CancelToken], OperationResult]


def defaults_of[P: Params](params_type: type[P]) -> P:
    """Build the all-defaults instance of a params dataclass."""
    return params_type()
