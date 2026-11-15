"""Run an operation in a child process so Cancel can terminate it.

The UI thread polls a pipe while the child owns the numpy work. Terminating the
process is the only reliable way to stop GrabCut, ONNX inference and model
downloads, so the process boundary is deliberate (PLAN.md section 5).
"""

from __future__ import annotations

import multiprocessing as mp
import traceback
from multiprocessing.connection import Connection
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from stickinator.core.ops.base import (
    Operation,
    OperationCancelled,
    Params,
    RGBAImage,
)

POLL_INTERVAL_MS = 40
CANCEL_GRACE_MS = 600
JOIN_TIMEOUT_S = 2.0


class ProcessCancelToken:
    """Cancel token backed by the child process's event."""

    def __init__(self, event: Any) -> None:
        self._event = event

    @property
    def cancelled(self) -> bool:
        return bool(self._event.is_set())

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise OperationCancelled


def _child_main(
    operation: Operation[Any],
    params: Params,
    image: RGBAImage,
    cancel_event: Any,
    connection: Connection,
) -> None:
    token = ProcessCancelToken(cancel_event)
    try:
        token.raise_if_cancelled()
        result = operation.run(image, params, token)
    except OperationCancelled:
        connection.send(("cancelled", None))
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}"
        connection.send(("error", detail))
    else:
        connection.send(("ok", result))
    finally:
        connection.close()


class OperationWorker(QObject):
    """Owns one child process at a time and reports its result on the UI thread."""

    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: Any = None
        self._connection: Connection | None = None
        self._cancel_event: Any = None
        self._cancelling = False

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll)

        self._grace_timer = QTimer(self)
        self._grace_timer.setSingleShot(True)
        self._grace_timer.setInterval(CANCEL_GRACE_MS)
        self._grace_timer.timeout.connect(self._terminate)

    @property
    def running(self) -> bool:
        return self._process is not None

    def start(
        self,
        operation: Operation[Any],
        params: Params,
        image: RGBAImage,
    ) -> None:
        """Run ``operation`` in a fresh process. Raises if one is already running."""
        if self.running:
            msg = "an operation is already running"
            raise RuntimeError(msg)

        context = mp.get_context("spawn")
        parent_connection, child_connection = context.Pipe(duplex=False)
        cancel_event = context.Event()
        process = context.Process(
            target=_child_main,
            args=(operation, params, image, cancel_event, child_connection),
            daemon=True,
        )
        process.start()
        child_connection.close()

        self._process = process
        self._connection = parent_connection
        self._cancel_event = cancel_event
        self._cancelling = False
        self._poll_timer.start()

    def cancel(self) -> None:
        """Ask the child to stop, then terminate it if it does not comply."""
        if not self.running:
            return
        self._cancelling = True
        if self._cancel_event is not None:
            self._cancel_event.set()
        self._grace_timer.start()

    def shutdown(self) -> None:
        """Terminate any child process without emitting a result."""
        if self._process is None:
            return
        self._stop_timers()
        if self._cancel_event is not None:
            self._cancel_event.set()
        self._join()
        self._release()

    @Slot()
    def _poll(self) -> None:
        connection = self._connection
        if connection is not None and connection.poll():
            try:
                status, payload = connection.recv()
            except EOFError:
                # A terminated child leaves a broken pipe behind.
                if self._cancelling:
                    status, payload = "cancelled", None
                else:
                    status, payload = "error", "the operation process closed unexpectedly"

            self._stop_timers()
            self._join()
            self._release()

            if status == "ok":
                self.finished.emit(payload)
            elif status == "cancelled":
                self.cancelled.emit()
            else:
                self.failed.emit(str(payload))
            return

        process = self._process
        if process is None or process.is_alive():
            return

        exit_code = process.exitcode
        was_cancelled = self._cancelling
        self._stop_timers()
        self._join()
        self._release()

        if was_cancelled:
            self.cancelled.emit()
        else:
            self.failed.emit(f"The operation process exited unexpectedly (code {exit_code}).")

    @Slot()
    def _terminate(self) -> None:
        process = self._process
        if process is not None and process.is_alive():
            process.terminate()

    def _join(self) -> None:
        process = self._process
        if process is None:
            return
        process.join(timeout=JOIN_TIMEOUT_S)
        if process.is_alive():
            process.terminate()
            process.join(timeout=JOIN_TIMEOUT_S)

    def _stop_timers(self) -> None:
        self._poll_timer.stop()
        self._grace_timer.stop()

    def _release(self) -> None:
        if self._connection is not None:
            self._connection.close()
        self._process = None
        self._connection = None
        self._cancel_event = None
        self._cancelling = False
