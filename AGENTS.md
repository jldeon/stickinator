# Agent notes

## Never open windows on the developer's desktop

Stickinator is a Qt GUI. Launching it while working pops a real window and a
Dock icon on the machine doing the work. Verify without showing anything:

- `make test` for behaviour, `make smoke` for a launch check. Both force
  `QT_QPA_PLATFORM=offscreen`.
- Do not run `make run`, `uv run stickinator`, `open dist/Stickinator.app`, or a
  bare script that constructs a `QApplication`, unless the task is explicitly
  about the real window.
- If a one-off Qt script is unavoidable, set `QT_QPA_PLATFORM=offscreen` before
  importing PySide6 and quit with `QTimer.singleShot(...)`; never leave an event
  loop running in the background.

## Tests

- No real modal dialogs in tests. Monkeypatch `_show_error`,
  `_ask_unsaved_changes`, `_ask_open_path`, `_ask_save_path` and
  `_confirm_overwrite_original`.
- pytest-qt closes registered widgets at teardown. Register windows with
  `qtbot.addWidget(window, before_close_func=...)` and mark the document clean,
  otherwise a deliberately-dirty window triggers the unsaved-changes prompt
  after `monkeypatch` has already been undone.

## Commits

- `make lint` and `make test` must pass before every commit.
- One commit per milestone, message `Milestone N: <short title>`.
- Never commit secrets, downloaded models, build output or `dist/`.
