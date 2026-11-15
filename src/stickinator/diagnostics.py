"""Headless self-test, used to verify a packaged build.

Run from the bundle:

    Stickinator.app/Contents/MacOS/Stickinator --self-test --self-test-out report.txt

Add ``--ai`` to also run one local rembg inference (downloads the model on first
use).
"""

from __future__ import annotations

import importlib
import platform
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

import numpy as np

MODULES = (
    "stickinator",
    "PySide6",
    "numpy",
    "cv2",
    "PIL",
    "rembg",
    "onnxruntime",
    "pymatting",
)


def run_self_test(use_ai: bool = False, report_path: Path | None = None) -> int:
    lines: list[str] = []
    success = True

    def emit(message: str) -> None:
        lines.append(message)
        print(message, flush=True)

    try:
        emit(f"python {sys.version.split()[0]} on {platform.platform()}")
        emit(f"frozen={getattr(sys, 'frozen', False)}")

        for module_name in MODULES:
            try:
                module = importlib.import_module(module_name)
            except Exception as exc:
                emit(f"{module_name} MISSING: {exc}")
                success = False
                continue
            found = getattr(module, "__version__", None)
            emit(f"{module_name} {found or 'imported'}")

        onnxruntime = importlib.import_module("onnxruntime")
        emit("onnxruntime providers: " + ", ".join(onnxruntime.get_available_providers()))

        if use_ai:
            success = _check_local_ai(emit) and success
    except Exception:
        emit(traceback.format_exc())
        success = False

    emit("self-test OK" if success else "self-test FAILED")
    if report_path is not None:
        try:
            report_path.write_text("\n".join(lines) + "\n")
        except OSError as exc:
            print(f"could not write {report_path}: {exc}", file=sys.stderr, flush=True)
            success = False
    return 0 if success else 1


def _check_local_ai(emit: Callable[[str], None]) -> bool:
    from stickinator.core.ai import local_rembg
    from stickinator.core.ai.config import LocalConfig
    from stickinator.core.ops.base import NeverCancelled

    emit("running local rembg (u2net)")
    image = np.zeros((64, 64, 4), dtype=np.uint8)
    image[...] = (240, 240, 240, 255)
    image[16:48, 16:48] = (200, 40, 40, 255)

    try:
        result = local_rembg.remove_background(image, LocalConfig(model="u2net"), NeverCancelled())
    except Exception:
        emit(traceback.format_exc())
        return False

    corner = int(result[0, 0, 3])
    centre = int(result[32, 32, 3])
    emit(f"rembg corner alpha={corner} centre alpha={centre}")
    if corner < 64 and centre > 191:
        emit("local rembg OK")
        return True
    emit("local rembg produced an unexpected cutout")
    return False
