"""Worker behaviour: success, errors, cooperative cancel and termination."""

from __future__ import annotations

import time
from collections.abc import Iterator

import numpy as np
import pytest
from PySide6.QtCore import QTimer
from pytestqt.qtbot import QtBot
from tests.helpers.fake_ops import FAIL, FILL, STUBBORN, FakeParams

from stickinator.ui.worker import OperationWorker

TIMEOUT_MS = 30_000


def _image() -> np.ndarray:
    image = np.zeros((16, 16, 4), dtype=np.uint8)
    image[..., 3] = 255
    return image


@pytest.fixture
def worker() -> Iterator[OperationWorker]:
    instance = OperationWorker()
    yield instance
    instance.shutdown()


def test_runs_an_operation_and_returns_pixels(worker: OperationWorker, qtbot: QtBot) -> None:
    with qtbot.waitSignal(worker.finished, timeout=TIMEOUT_MS) as blocker:
        worker.start(FILL, FakeParams(value=42, color=(0, 200, 0)), _image())

    result = blocker.args[0]
    assert isinstance(result, np.ndarray)
    assert result[0, 0, 0] == 42
    assert result[0, 0, 1] == 200
    assert not worker.running


def test_reports_an_exception_from_the_operation(worker: OperationWorker, qtbot: QtBot) -> None:
    with qtbot.waitSignal(worker.failed, timeout=TIMEOUT_MS) as blocker:
        worker.start(FAIL, FakeParams(), _image())

    assert "RuntimeError: boom" in blocker.args[0]
    assert not worker.running


def test_cancel_stops_a_cooperative_operation(worker: OperationWorker, qtbot: QtBot) -> None:
    started = time.monotonic()

    with qtbot.waitSignal(worker.cancelled, timeout=TIMEOUT_MS):
        worker.start(FILL, FakeParams(delay=30.0), _image())
        QTimer.singleShot(300, worker.cancel)

    assert time.monotonic() - started < 5.0
    assert not worker.running


def test_cancel_terminates_an_operation_that_ignores_the_token(
    worker: OperationWorker, qtbot: QtBot
) -> None:
    started = time.monotonic()

    with qtbot.waitSignal(worker.cancelled, timeout=TIMEOUT_MS):
        worker.start(STUBBORN, FakeParams(delay=30.0), _image())
        QTimer.singleShot(200, worker.cancel)

    # Cooperative grace is 600 ms, then the process is killed.
    assert time.monotonic() - started < 10.0
    assert not worker.running


def test_rejects_a_second_start(worker: OperationWorker, qtbot: QtBot) -> None:
    with qtbot.waitSignal(worker.finished, timeout=TIMEOUT_MS):
        worker.start(FILL, FakeParams(delay=0.4), _image())
        with pytest.raises(RuntimeError, match="already running"):
            worker.start(FILL, FakeParams(), _image())


def test_shutdown_stops_the_child_without_signals(worker: OperationWorker, qtbot: QtBot) -> None:
    worker.start(STUBBORN, FakeParams(delay=30.0), _image())
    qtbot.wait(200)

    worker.shutdown()

    assert not worker.running
