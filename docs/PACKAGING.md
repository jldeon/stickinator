# Packaging notes (macOS)

How the `.app` and `.dmg` are produced, and what the milestone 1 packaging spike
proved.

## Build

`make build` runs `scripts/build_macos.sh`, which:

1. builds `dist/Stickinator.app` from `packaging/stickinator.spec` with
   PyInstaller (onedir, windowed),
2. ad-hoc signs the bundle (`codesign --force --deep --sign -`),
3. wraps it in `dist/Stickinator.dmg` with `hdiutil`.

The result is unsigned and not notarized; see the README for Gatekeeper.

## Spike results (2026-11-15)

A throwaway console build using the same collection rules, on macOS 26.6.2
(arm64) with Python 3.12.16:

| check | result |
| --- | --- |
| `rembg` 2.0.87 import | pass |
| `onnxruntime` 1.32.0 import | pass |
| `pymatting` import (numba/llvmlite) | pass |
| CPU inference (`u2net`) | pass |
| alpha matting | pass |
| CoreML session + inference | pass |
| execution providers available | CoreML, Azure, CPU |

Two consequences: alpha matting can ship in v1, and the CoreML option is viable.
The frozen bundle is about 390 MB, mostly onnxruntime, PySide6 and the model
runtime; trim it in milestone 9 if needed.

## Verifying a build

The bundle can prove itself without opening a window:

```sh
dist/Stickinator.app/Contents/MacOS/Stickinator --self-test --self-test-out /tmp/report.txt
dist/Stickinator.app/Contents/MacOS/Stickinator --self-test --ai --self-test-out /tmp/report-ai.txt
```

`--ai` runs one local rembg inference and downloads the model on first use.
A milestone 9 build (macOS 26.6.2, arm64) reported:

- frozen bundle, Python 3.12.16
- PySide6 6.12.0, numpy 2.5.4, OpenCV 4.14.0, Pillow 13.0.0
- rembg 2.0.87, onnxruntime 1.32.0, pymatting 1.1.16
- execution providers: CoreML, Azure, CPU
- local rembg cutout: corner alpha 0, centre alpha 255

Sizes: about 496 MB for the `.app` and 203 MB for the `.dmg`.

## What the spec encodes

- `collect_all` for `rembg`, `pymatting`, `onnxruntime`, `numba` and `llvmlite`,
  because none of them are discovered from imports alone.
- `collect_submodules("rembg.sessions")`: rembg looks models up by name at
  runtime.
- Exclude PySide6 WebEngine/Pdf. The app depends on `PySide6-Essentials` only.
- `console=False`, so the packaged app has no stdout. Diagnostics must go to a
  log file or a dialog.

## Known future issue

The process-based worker in `PLAN.md` section 5 uses `multiprocessing`. A frozen
macOS app must use the `spawn` start method and the entry point must call
`multiprocessing.freeze_support()` before any child process is created.
