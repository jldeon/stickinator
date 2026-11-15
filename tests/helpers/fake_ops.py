"""Operation parameters and runnable fakes used by tests.

These live in an importable module because ``multiprocessing`` with the spawn
start method pickles the callable by reference: the child process has to be able
to import it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from stickinator.core.ops.base import (
    CancelToken,
    Operation,
    OperationContext,
    OperationResult,
    Params,
    RGBAImage,
)


@dataclass(frozen=True, slots=True)
class FakeParams(Params):
    value: int = 1
    delay: float = 0.0
    color: tuple[int, int, int] = (255, 0, 0)
    enabled: bool = True


def fill(
    image: RGBAImage,
    params: FakeParams,
    context: OperationContext,
    cancel: CancelToken,
) -> OperationResult:
    deadline = time.monotonic() + params.delay
    while time.monotonic() < deadline:
        cancel.raise_if_cancelled()
        time.sleep(0.02)

    result = image.copy()
    result[..., 0] = params.value
    result[..., 1] = params.color[1]
    return OperationResult(result)


def fail(
    image: RGBAImage,
    params: FakeParams,
    context: OperationContext,
    cancel: CancelToken,
) -> OperationResult:
    raise RuntimeError("boom")


def stubborn(
    image: RGBAImage,
    params: FakeParams,
    context: OperationContext,
    cancel: CancelToken,
) -> OperationResult:
    """Ignore the token entirely, so only termination can stop it."""
    time.sleep(params.delay or 30.0)
    return OperationResult(image)


def report_dpi(
    image: RGBAImage,
    params: FakeParams,
    context: OperationContext,
    cancel: CancelToken,
) -> OperationResult:
    result = image.copy()
    result[..., 0] = int(context.dpi[0])
    return OperationResult(result, dpi=context.dpi)


FILL = Operation(key="fake.fill", label="Fill", params_type=FakeParams, run=fill)
FAIL = Operation(key="fake.fail", label="Fail", params_type=FakeParams, run=fail)
STUBBORN = Operation(key="fake.stubborn", label="Stubborn", params_type=FakeParams, run=stubborn)
REPORT_DPI = Operation(key="fake.dpi", label="Report DPI", params_type=FakeParams, run=report_dpi)
