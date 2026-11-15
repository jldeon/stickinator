# Stickinator

Turn images into printable, cut-ready stickers.

Open an image, remove its background, pad or outline it, then save a PNG with
transparency and print resolution set. See [PROJECT.md](PROJECT.md) for the
requirements and [PLAN.md](PLAN.md) for the build plan.

## Requirements

- Apple Silicon Mac running macOS 14 or later
- [Xcode Command Line Tools](https://developer.apple.com/xcode/resources/) (`xcode-select --install`)
- Network access on first setup

Nothing else needs to be installed by hand: `scripts/bootstrap.sh` installs
`uv` and CPython 3.12 if they are missing.

## Setup

```sh
make setup
```

## Run

```sh
make run
```

## Test and lint

```sh
make test
make lint
```

Tests run with `QT_QPA_PLATFORM=offscreen`, so no window server is needed.

## Build

```sh
make build
```

Produces `dist/Stickinator.app` and `dist/Stickinator.dmg`. The app is unsigned.

macOS Gatekeeper blocks unsigned apps on first launch. Either right-click the
app and choose **Open**, or clear the quarantine flag:

```sh
xattr -dr com.apple.quarantine /Applications/Stickinator.app
```

## AI background removal

Three providers are supported: a local `rembg` model (offline), a generic HTTP
endpoint, and an OpenAI-compatible `/v1/images/edits` endpoint.

- Local models download on first use and are stored in `~/.u2net` by default
  (override with the `U2NET_HOME` environment variable, or in Settings).
  `isnet-general-use` is about 170 MB; `birefnet-general` is about 930 MB.
- API keys are stored in the macOS Keychain, never in settings files or logs.
- Because the app is unsigned, macOS may ask for Keychain access again after
  each rebuild. That is expected.

## Project layout

```
src/stickinator/    application code (core/ has no Qt imports)
packaging/          PyInstaller spec and bundle metadata
scripts/            bootstrap and build scripts
tests/              pytest suite
```

## Status

Milestone 2: core image document, file I/O and undo. The window is still a
shell; the preview and operation buttons arrive in milestone 3.
