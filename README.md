# Stickinator

Turn images into printable, cut-ready stickers. Open a JPEG, PNG or WEBP,
remove the background, add an outline or padding, then save an RGBA PNG with
print resolution embedded.

`PROJECT.md` is the requirements document. `PLAN.md` records the design
decisions and milestones.

## Requirements

- Apple Silicon Mac running macOS 14 or later
- [Xcode Command Line Tools](https://developer.apple.com/xcode/resources/) (`xcode-select --install`)
- Network access for the first setup and for AI model downloads

Nothing else needs installing by hand: `scripts/bootstrap.sh` installs `uv` and
CPython 3.12 when they are missing.

## Setup and run

```sh
make setup
make run
```

## Workflow

1. **Open** an image with the button, ⌘O, or by dragging a PNG/JPEG/WEBP onto
   the window.
2. **Run operations** from the right-hand column. Each opens a dialog filled
   with the values from the last run; those values survive restarts.
3. **Undo** (⌘Z) steps back through the image history. There is no redo.
4. **Save** (⌘S) writes an RGBA PNG with the DPI in `pHYs`. The first save
   suggests `<name>_sticker.png`; Save As (⌘⇧S) always asks. Saving over the
   file you opened requires confirmation.

Closing, quitting, or opening another file with unsaved changes asks whether to
Save, Discard or Cancel.

### Shortcuts

| Action | Shortcut |
| --- | --- |
| Open | ⌘O |
| Save | ⌘S |
| Save As | ⌘⇧S |
| Undo | ⌘Z |
| Settings | ⌘, |
| Close window | ⌘W |
| Quit | ⌘Q |

## Operations

| Operation | Options |
| --- | --- |
| **Remove BG** | Colour key or GrabCut. Colour key: automatic edge colour or eyedropper, ΔE76 tolerance 0–100, contiguous or global matching, edge feather, despeckle. GrabCut: inset as percent or pixels, iterations. |
| **Remove BG (AI)** | Local rembg, generic HTTP endpoint, or OpenAI-compatible edits. Optional alpha binarisation with a threshold. |
| **Extend Canvas** | Uniform or per-side margins in px, percent or inches; keep the content centred. |
| **Border** | Width in px or inches, colour, content alpha threshold, outer-outline-only hole filling, piece merging (close or convex hull), smoothing, solid alpha, auto-extended canvas. |
| **Trim** | Alpha threshold and optional margin. |
| **Resize / Print Size** | Pixels, inches or centimetres, DPI, aspect lock, resampling method, and a DPI-only mode that leaves pixels untouched. |

Every operation runs in a child process. Cancel terminates it, which is the only
reliable way to stop GrabCut and ONNX inference. Results are undoable and are
applied only after the operation finishes.

## AI background removal

The provider is chosen in Settings (⌘,) and can be overridden per run.

- **Local (rembg)** — offline after the first download, no API key.
  - Models: `isnet-general-use` (about 170 MB, default), `u2net` (about
    176 MB), `birefnet-general` (about 930 MB).
  - Models live in `~/.u2net` unless a different folder is set in Settings.
  - Alpha matting is available; it is slower because it uses numba.
  - CoreML acceleration is optional and falls back to the CPU when the graph
    cannot load.
- **Generic HTTP** — multipart POST with a configurable image field name, auth
  header and format, plus extra headers and form fields. Works with remove.bg,
  rembg-server and similar services.
- **OpenAI-compatible `/v1/images/edits`** — configurable base URL, model and
  prompt. Sends `background: "transparent"` and `output_format: "png"`, retries
  without them for older servers, and accepts either `b64_json` or a `url`
  response.

Only the provider's alpha channel is used; the original pixels keep their
colour, so remote services cannot shift the subject's colours. A returned
image at the wrong size is resized back to the document.

### API keys

Keys are stored in the macOS Keychain through `keyring`, never in settings files
or logs. If the keychain is unavailable, the app says so and keeps the key for
the session only.

The app is unsigned, so each rebuild is a new binary identity and macOS may ask
for Keychain access again after an update. That is expected.

## Settings

Settings (⌘,) covers:

- default provider, request timeout
- local model, alpha matting thresholds, erode size, CoreML, model folder
- generic HTTP URL, field, auth header/format, extra headers and fields
- OpenAI base URL, model and prompt
- API keys for the two remote providers
- default DPI and the undo memory limit

## Build

```sh
make build
```

Produces `dist/Stickinator.app` and `dist/Stickinator.dmg`. The app is unsigned
but ad-hoc signed; see `docs/PACKAGING.md` for what the spec bundles and why.
A current build is about 496 MB for the app and 203 MB for the disk image.

macOS Gatekeeper blocks unsigned apps on first launch. Right-click the app and
choose **Open**, or clear the quarantine flag:

```sh
xattr -dr com.apple.quarantine /Applications/Stickinator.app
```

## Troubleshooting

- **A build check without opening a window**:

  ```sh
  dist/Stickinator.app/Contents/MacOS/Stickinator --self-test --self-test-out /tmp/report.txt
  dist/Stickinator.app/Contents/MacOS/Stickinator --self-test --ai --self-test-out /tmp/report-ai.txt
  ```

  `--ai` runs one local rembg inference and downloads the model on first use.
- **Model download seems stuck** — the first run of a model downloads up to
  930 MB. A partial download is deleted and retried on the next run.
- **Cancel takes a moment** — operations get 0.6 s to stop cooperatively, then
  the worker process is terminated.
- **Keychain prompts after each rebuild** — expected for unsigned builds.

## Development

```sh
make test          # unit and UI tests, offscreen
make lint          # ruff check, ruff format --check, mypy
make smoke         # headless launch check
make test-network  # downloads rembg models; not run in CI
```

`src/stickinator/core` must not import Qt — an architecture test enforces it.
All Qt code lives in `src/stickinator/ui`. Long-running work crosses the process
boundary through `ui/worker.py`.

```
src/stickinator/
  core/          image document, I/O, operations, AI providers
  ui/            window, preview, dialogs, settings, worker
packaging/       PyInstaller spec
scripts/         bootstrap, build, headless smoke check
tests/           pytest suite
docs/            packaging and future Windows notes
```

See `docs/PACKAGING.md` for build internals and `docs/WINDOWS.md` for the future
Windows port.

## Status

Milestone 10: feature complete for v1. All six operations, undo, drag-and-drop,
settings, the keychain-backed AI providers, and the unsigned `.app`/`.dmg`
build are in place.
