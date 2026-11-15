# PLAN.md — Stickinator v1

This plan is for the agent that will build the app. `PROJECT.md` is the source of truth for requirements. This plan contains the design decisions made with the project owner, plus the order to do the work in.

## 0. Summary
Stickinator is a desktop app for Apple Silicon Macs, built in Python with PySide6 (Qt). It turns images into stickers that are ready to print and cut. Windows 11 support comes later, so the code must stay portable:
- Don't use macOS-only APIs.
- Handle paths with `pathlib`, and look up app folders with `QStandardPaths`.
- Keep platform-specific code in clearly marked, separate places.

## 1. Tech stack and tooling
- **Python 3.12**, managed with **uv** (`pyproject.toml` + `uv.lock`).
  - `scripts/bootstrap.sh` installs uv if it is missing, then installs and pins CPython 3.12 (`uv python install 3.12`, `uv python pin 3.12`). The Homebrew Python (3.14) is not used.
- **Runtime libraries:**
  - `PySide6-Essentials` — not the full `PySide6`, which also pulls in WebEngine and Pdf and roughly doubles install and bundle size. The app only needs QtCore/QtGui/QtWidgets.
  - `numpy`, `opencv-python-headless` (pin `~=4.14`), `Pillow`, `httpx`, `keyring`.
  - `rembg` **plus an explicit `onnxruntime` dependency.** As of rembg 2.0.87, onnxruntime is no longer a rembg dependency; it must be listed here or the local provider fails at import.
  - rembg itself forces `numpy>=2.3` and `pillow>=12.3,<14`, and hard-requires `pymatting` (which pulls in `numba` + `llvmlite`), plus `scikit-image`, `scipy` and `pooch`. This is the largest packaging risk in the project; see the milestone 1 spike.
  - Import `rembg` only when the local AI provider is actually used, so the app starts fast.
- **Developer tools:** `pytest`, `pytest-qt`, `ruff`, `mypy`, `pyinstaller`.
- **Packaging:** PyInstaller builds an unsigned `.app`, and `hdiutil` wraps it in a `.dmg`.
  - The spec lives at `packaging/stickinator.spec` and **is committed** (see the `.gitignore` note in section 2).
  - The spec must collect the data files and libraries for `rembg`, `onnxruntime`, `pymatting`, `numba` and `llvmlite`, and must keep PySide6 Addons/WebEngine out.
  - Ad-hoc sign the bundle in the build script (`codesign -s - --force --deep`). Users will still be re-prompted for keychain access after each rebuild, because every build is a new binary identity; document that.
  - Minimum supported macOS version: **14** (the floor set by the PySide6 6.x and onnxruntime wheels).
- **Scripts:**
  - `scripts/bootstrap.sh`: installs uv if it's missing, installs Python 3.12, then runs `uv sync`.
  - `scripts/build_macos.sh`: builds `dist/Stickinator.app` and `dist/Stickinator.dmg`.
  - `Makefile` targets: `setup`, `run`, `test`, `lint`, `build`, `clean`.
- **CI:** a GitHub Actions workflow on `macos-15` runs ruff, mypy and pytest.
  - Use `astral-sh/setup-uv` with dependency caching, `uv python install 3.12`, and `uv sync --locked`.
  - Run tests with `QT_QPA_PLATFORM=offscreen`. Without it, pytest-qt fails on a headless runner.
  - Skip tests that download rembg models: mark them `@pytest.mark.network` and run `pytest -m "not network"`.
  - Add `ruff format --check` alongside `ruff check`, and `uv lock --check` so a stale lockfile fails CI.
- **README.md** must cover:
  - how to set up, run and build
  - how to configure the AI providers
  - where rembg stores its models
  - how to open an unsigned app past Gatekeeper (right-click → Open, or `xattr -dr com.apple.quarantine`)

## 2. Version control (required)
- The working copy lives on **local disk** at `~/projects/stickinator`. Don't develop directly on the SMB share: a network write already zero-filled `PLAN.md` once, and `.app` builds plus `codesign` depend on real symlinks and extended attributes.
- The project folder is **not** a git repository yet. Run `git init` in Milestone 1.
- Add a `.gitignore` that ignores:
  - `.venv/`, `dist/`, `build/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
  - build output: `*.dmg`, `*.app`
  - downloaded models: `models/`, `*.onnx`
  - macOS clutter: `.DS_Store` and `._*`
  - editor swap files: `.*.swp`
- Do **not** ignore `*.spec`. The PyInstaller spec at `packaging/stickinator.spec` is source and must be committed.
- **Commit at the end of every milestone in section 9**, and only after `make lint` and `make test` pass.
  - Message format: `Milestone N: <short title>`, with a body listing the main changes.
  - If a milestone is large, smaller commits along the way are fine. The milestone must still end with a commit where everything passes.
  - Never commit secrets, API keys, downloaded model files or build output.

## 3. Project layout
```
src/stickinator/
  __main__.py, app.py
  core/              # pure image logic — MUST NOT import Qt
    image_doc.py     # Document: RGBA ndarray, source path, DPI, dirty flag, undo stack
    io.py            # load / save
    ops/
      base.py        # Operation protocol: name, Params dataclass, run(img, params, cancel) -> img
      bg_algorithmic.py, bg_ai.py, extend_canvas.py, border.py, trim.py, resize.py
    ai/
      provider.py    # Provider protocol + registry
      generic_post.py, openai_edits.py, local_rembg.py
    settings.py      # QSettings-free settings model; persistence adapter lives in ui/
  ui/
    main_window.py, preview_widget.py, worker.py, settings_store.py
    dialogs/         # one dialog per operation + settings_dialog.py
packaging/           # stickinator.spec, Info.plist
tests/
scripts/
```

## 4. Core model
- The image is always stored in memory as an **RGBA uint8 numpy array** with shape (H, W, 4).
- **Undo:**
  - Undo is a stack of image snapshots. It goes back as many steps as the history allows. There is **no redo**.
  - The stack has a memory limit (default 512 MB, changeable in Settings). When it's over the limit, the oldest snapshots are dropped. 512 MB rather than 1 GB because rembg keeps a model resident in memory.
  - A snapshot holds the image **and** the DPI, so "Set DPI only" is undoable.
  - The Undo button is disabled when there's nothing to undo.
- **Dirty flag:** set when any operation runs, cleared when the file is saved.
- **Loading files** (`io.py`):
  - Accept JPEG, PNG and WEBP. For animated WEBP, use the first frame.
  - Rotate the image according to its EXIF orientation tag.
  - Convert the colors to sRGB using the embedded ICC profile.
  - Convert CMYK, palette, grayscale and 16-bit images to RGBA8.
  - Read the DPI from the file. If there isn't one, use the default DPI from Settings (300).
- **Saving files:**
  - Always save as a PNG with transparency (RGBA), with the DPI stored in the PNG `pHYs` chunk.
  - Use a "Save As" dialog that suggests `<name>_sticker.png`.
  - Never overwrite the original file without asking first.
  - After the first Save As, ⌘S writes to that path silently; only "Save As…" prompts again.
  - Write atomically: save to a temp file in the same directory, flush and `fsync`, then `os.replace`. An interrupted write must never truncate or zero an existing file.

## 5. Main UI
- **Preview (left side):**
  - Fits the image to the available space and keeps its aspect ratio.
  - Shows a checkerboard behind transparent areas.
  - Has a status line with the size in pixels, the DPI and the print size in inches and cm.
- **Button column (right side):** Open, Remove BG, Remove BG (AI), Extend Canvas, Border, Trim, Resize / Print Size, Undo, Save.
  - Every button except Open is disabled until an image is loaded. Settings… stays enabled always; Save and Undo follow the dirty and undo state.
- **Ways to open a file:** the Open button, ⌘O, or dragging a file onto the window.
- **Menus and shortcuts:** ⌘O, ⌘S, ⌘Z, and Settings… (⌘,).
- **Unsaved-changes prompt** appears when closing the window, opening another file, or quitting. Choices: Save / Discard / Cancel.
- **Long-running operations** (AI calls, GrabCut, large borders, rembg model downloads) run in a **child process**, driven from the UI thread by `worker.py`:
  - While one runs, show a busy indicator and disable the buttons.
  - Cancel terminates the child process. This is required, not optional: `cv2.grabCut` is a single blocking call, ONNX inference cannot be interrupted, and `pooch` downloads cannot be aborted. A cooperative cancel token alone cannot satisfy the requirement.
  - Core operations still take a cancel token and check it at step boundaries, so the common case cancels cheaply before the process is killed.
  - If an operation fails or is cancelled, show a message box and leave the image unchanged.

## 6. Parameter dialogs
- Each operation opens a modal dialog. `Params` dataclasses define the values; the widgets are written per operation, because colour pickers, eyedroppers and unit selectors don't map cleanly onto generated forms.
- Dialogs are pre-filled with the last values used for that operation. Those values are saved in `QSettings` under one key per operation (serialized as JSON with a schema version), so they **persist across app restarts**. On a decode failure or version mismatch, fall back to defaults instead of raising.
- Each dialog has a "Reset to defaults" button.
- Stretch goal: a live preview inside the dialog for fast operations only.

## 7. Operations

### 7.1 Background removal (algorithmic): two modes, chosen in the dialog
- **Color key / flood fill**
  - **Background color source:**
    - automatic: the most common color among the pixels along the image edges
    - or a color the user picks, with a color picker and an eyedropper that samples a point in the preview
  - **Settings:**
    - tolerance from 0 to 100, measured as CIE Lab distance using ΔE76 (plain Euclidean distance in Lab), mapped 1:1 to ΔE units. ΔE94 and ΔE2000 are not used.
    - mode:
      - *contiguous*: flood fill outward from starting points (edge pixels that match, or a point the user clicks)
      - *global*: remove every pixel that matches
    - edge feather in pixels
    - despeckle: remove leftover islands smaller than N pixels (8-connectivity)
  - **Requirement:** this must work when the background touches **no** edges (which is why the user-clicked starting point and global mode exist). It must also work when the foreground touches one or more edges.
- **GrabCut**
  - OpenCV GrabCut, starting from a rectangle inset from the image edges.
  - Settings: inset (as a % or in px) and number of iterations.
  - `cv2.grabCut` is one blocking call (OpenCV 4.14 has no per-iteration mode), so cancellation is handled by terminating the worker process (section 5).
- **Tests:** synthetic images where:
  - the subject touches 0, 1, 2 or 4 edges
  - background color is enclosed inside the subject
  - colors are close to the tolerance limit
  - alpha masks are compared with an IoU tolerance (≥ 0.98), not exact equality.

### 7.2 Background removal (AI)
- A `Provider` protocol that takes RGBA input, returns RGBA output and accepts a cancel token. Three providers are chosen in Settings, and the operation dialog can override the choice.
  1. **Local (rembg)**: works offline and needs no API key.
     - Settings:
       - model: `u2net` (~176 MB), `isnet-general-use` (default, ~170 MB) or `birefnet-general` (~928 MB download)
       - alpha matting on/off, with its foreground, background and erode settings
     - Models download automatically the first time they're used. Show progress or a busy state and explain the download in the UI, including the size. `pooch` has no resume support, so delete a partial download and retry.
     - The model folder is configurable. By default it's rembg's standard folder (`~/.u2net`, set with `U2NET_HOME`).
     - Use the CPU execution provider by default. Offer the CoreML execution provider as an option if it's available, and fall back to CPU if it fails.
     - rembg's `new_session(..., providers=[...])` accepts an explicit provider list and warns when onnxruntime falls back to CPU; use that rather than environment variables.
     - Load the session once and cache it for reuse.
  2. **Generic POST**: send the image as multipart form data, get PNG bytes back.
     - Configurable: URL, form field name, auth header name and value format (for example `X-Api-Key: {key}` or `Authorization: Bearer {key}`), extra form fields and headers.
     - Works with remove.bg, rembg-server and similar services.
     - Accept any image content type in the response; decode with Pillow rather than assuming PNG.
  3. **OpenAI-compatible `/v1/images/edits`**
     - Configurable: base URL, model and prompt.
     - Default prompt: remove the background, keep the subject unchanged, transparent background.
     - Send `background: "transparent"` and `output_format: "png"`. A prompt alone does not produce alpha. Tolerate servers that reject or ignore those fields, and treat a fully opaque result as a provider error rather than silently returning the original image.
     - The response may contain the image as base64 (`b64_json`) or as a `url`. Handle both.
- **API keys** are stored with `keyring` (the Keychain on macOS) and are **never** written to `QSettings` or logs.
- **Dialog options:**
  - provider override
  - "Binarize alpha" post-processing, with a threshold
- **Remote requests:** set a timeout, allow cancelling, and show a clear error message for HTTP errors.
- If the result comes back at a different size from the input, resize it back to the original dimensions.
- Take the provider's **alpha** and apply it to the **original RGB** pixels rather than using the provider's RGB. That avoids colour shifts and JPEG fringing from remote services.
- **Tests:**
  - remote providers use an `httpx.MockTransport`
  - the local provider gets a unit test with rembg mocked, plus one `network`-marked integration test

### 7.3 Extend canvas
- **Settings:**
  - mode: uniform or per side
  - units: px, % or inches (inches use the image's DPI)
  - "Keep centered", on by default. Uniform mode is always centered.
- The new area is transparent. Nothing is scaled or cropped.

### 7.4 Border (sticker outline)
- **Dialog settings** (each listed behavior is a toggle):
  - width, in px or inches
  - color
  - content alpha threshold (default 128)
  - **Outer outline only**: fill interior holes. Default on. The fill uses the border color, since the original image is composited on top afterwards and its alpha-0 holes would otherwise make the fill invisible.
  - **Merge separate pieces**: close gaps between pieces, using either a morphological close with a set radius or a convex hull. Default on. Morphological close is the default method; the hull is opt-in because it can swallow large concave gaps.
  - **Smooth / rounded outline**: blur the mask and re-threshold it, with a smoothing amount setting. Default on.
  - **Solid alpha**: pixels are either fully opaque or fully transparent, so cutting software traces the edge cleanly. Default on.
  - **Auto-extend canvas** so the border is never cut off. Default on.
- **Algorithm:**
  1. Build a mask of pixels with alpha ≥ the threshold.
  2. If merge is on, apply the close or the convex hull.
  3. If outer-only is on, fill the holes in the mask.
  4. If auto-extend is on, pad the canvas by the border width plus the smoothing margin.
  5. Grow the mask outward by the border width, using a Euclidean distance transform so the width is exact.
  6. If smoothing is on, smooth the grown mask, then re-threshold. Compensate the growth distance by the smoothing offset so the measured width stays accurate.
  7. Fill the grown mask with the border color, then draw the original image on top.
  8. If solid alpha is on, set every pixel's alpha to either 0 or 255.
- **Tests:**
  - the border width is accurate to within 1 px
  - nothing is cut off when auto-extend is on
  - there is exactly one outer outline when merge and outer-only are both on
  - when solid alpha is on, every alpha value is 0 or 255
  - interior holes are filled with the border color, not left transparent

### 7.5 Trim transparent padding
- Crop to the bounding box of pixels whose alpha is above a threshold (same default 128 as the border), then add an optional margin in pixels.
- If the image is completely transparent, show an error and leave the image unchanged.

### 7.6 Resize / print size
- **Settings:**
  - target width and/or height, in px, in or cm
  - DPI
  - lock aspect ratio (default on). If width, height and lock are all set, width wins and height is derived.
  - resampling method (default Lanczos)
- "Set DPI only" mode changes the print size without resampling the pixels.
- Resize with premultiplied alpha so no dark fringes appear around edges.

## 8. Settings dialog
- **AI:**
  - default provider
  - settings for each provider (section 7.2)
  - API key fields, saved to the keychain
  - timeout
- **General:**
  - default DPI
  - undo memory limit
  - rembg model folder
- Save settings with `QSettings`. Save secrets with `keyring`.
- If the keyring backend is unavailable, report it and keep the key in memory for the session. Never fall back to writing a key to disk.

## 9. Milestones
Do these in order. Each milestone must end with `make lint` and `make test` passing, followed by a **git commit** (see section 2).

1. **Scaffold:** `git init`, `.gitignore`, uv project, scripts, Makefile, CI workflow, README skeleton, an empty window that launches. Commit.
   - **Packaging spike belongs here, not in milestone 9:** a throwaway PyInstaller build that imports `rembg` + `onnxruntime` + `pymatting` and runs one inference. Numba/llvmlite bundling is the biggest technical risk; settle whether alpha matting ships in v1, and whether CoreML works, before any UI depends on it.
2. **Core document:** `Document`, file loading and saving (EXIF orientation, ICC, DPI, atomic write), undo stack with memory limit, unit tests. Commit.
3. **Main window:**
   - preview with checkerboard and status line
   - Open, Save and Undo
   - drag-and-drop
   - unsaved-changes prompt
   - enabling and disabling buttons
   - pytest-qt smoke tests

   Commit.
4. **Operation framework:**
   - Params dataclasses
   - per-operation dialogs
   - remembering settings across restarts
   - process-based worker with terminate-on-cancel and error handling
   - tests for settings persistence and cancellation

   Commit.
5. **Extend canvas, Trim, Resize/DPI**, with tests. Commit.
6. **Border**, with tests. Commit.
7. **Algorithmic background removal** (color key and GrabCut, with the eyedropper), with tests. Commit.
8. **AI background removal:** provider protocol, local rembg, generic POST, OpenAI edits, Settings dialog, keychain, tests. Commit.
9. **Packaging:** PyInstaller `.app` (including the rembg and onnxruntime files) and `.dmg` build script. Confirm the packaged app launches and that local rembg works inside it. Commit.
10. **Polish:**
    - shortcuts and menus
    - error messages
    - finish the README
    - `docs/WINDOWS.md` with notes on the future Windows port: PyInstaller on Windows, Credential Manager through keyring, onnxruntime DirectML

    Commit.

## 10. Acceptance criteria
- `make setup && make run` works on a fresh Apple Silicon Mac running macOS 14 or later that has only the Xcode Command Line Tools installed.
- `make build` produces `dist/Stickinator.app` and `dist/Stickinator.dmg`.
- Every operation has unit tests, and CI passes.
- Saved files are always RGBA PNGs with DPI metadata.
- Local rembg background removal works offline once its model has been downloaded.
- The git history has at least one commit per milestone.

## 11. Out of scope for v1
- Redo
- Batch processing
- Code signing and notarization
- Windows builds (but keep the code portable)
- Exporting cut paths as SVG/DXF
- Bundling rembg models inside the app (they download on first use)

## 12. Remaining small decisions
These don't block milestone 1, but confirm them before the milestone that needs them:
- Preview zoom/pan is out of scope, so the eyedropper needs either a magnified sample or a 3×3 average to be usable on a downscaled large image.
- DPI is stored as a single value and written to both axes of `pHYs`; per-axis source values are collapsed.
- Logging: write to a rotating file under `QStandardPaths.AppDataLocation`, never log API keys or image paths at info level.
- App icon/`.icns` and the `.dmg` background are cosmetic and can wait until milestone 10.
