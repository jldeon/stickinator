# Windows port notes

Windows 11 (x86) is a medium-priority roadmap item; v1 targets macOS only. This
file records what a port needs so the code stays portable.

## What is already portable

- `core/` contains no platform code: numpy, OpenCV, Pillow and httpx only.
- Paths use `pathlib`; application folders come from `QStandardPaths`.
- `keyring` already supports Windows Credential Manager with no extra
  dependency, using the same service and key names
  (`stickinator` / `<provider>-api-key`).
- The worker uses `multiprocessing` with the `spawn` start method and the entry
  point calls `freeze_support()`, which is what Windows needs.
- Qt provides the file dialogs, drag-and-drop and high-DPI handling.

## Platform-specific pieces to replace

| macOS | Windows |
| --- | --- |
| `hdiutil` disk image (`scripts/build_macos.sh`) | Inno Setup or WiX installer |
| `codesign -s -` ad-hoc signing | optional Authenticode signing |
| CoreML execution provider | `onnxruntime-directml` with `DmlExecutionProvider` |
| `~/.u2net` default model folder | consider `%LOCALAPPDATA%\Stickinator\models` |
| `.app` bundle via PyInstaller `BUNDLE` | `onedir` build plus a shortcut |

Keep `scripts/build_macos.sh` untouched and add a separate
`scripts/build_windows.ps1`, so no macOS-only command runs on Windows.

## Packaging

- Add `packaging/windows.spec` as a copy of `stickinator.spec` without
  `BUNDLE`/`info_plist`; use `EXE(..., console=False)` and `COLLECT`.
- Keep the `collect_all` set for `rembg`, `pymatting`, `onnxruntime`, `numba`
  and `llvmlite`; these are the same packaging risks as on macOS.
- PySide6 Addons/WebEngine must stay excluded; the app depends on
  `PySide6-Essentials`.
- Test the frozen build with the same `--self-test` flag:
  `Stickinator.exe --self-test --ai --self-test-out report.txt`.

## Acceleration

Local rembg config has a single `use_coreml` flag. On Windows, map that option
to DirectML rather than CoreML:

```python
providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
```

The existing fallback (retry without an accelerated provider) already covers
machines where DirectML is unavailable.

## CI

- Add a `windows-latest` job running `uv sync --locked`, `ruff`, `mypy` and
  `pytest -m "not network"` with `QT_QPA_PLATFORM=offscreen`.
- Build the installer on a tag, not on every pull request; it is slow.
- Keep the macOS job as the primary check until the port is complete.

## Risks to check on a real machine

- High-DPI scaling and font metrics in the dialogs.
- Drag-and-drop from Explorer (local files only; the code already checks
  `isLocalFile` and the suffix).
- Credential Manager prompts for unsigned executables.
- Antivirus/SmartScreen warnings for an unsigned installer.
- PyInstaller and numba/llvmlite behaviour on Windows, which differs from
  macOS enough that the milestone 1 packaging spike should be repeated.
