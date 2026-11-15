# Stickinator

This project contains an application used for automated image editing.  The intent of the tool is to take images and modify them in ways that make them easy to print and cut using external/3rd party sticker creating tools.

The main UI consists of an image preview on the left, and a vertical row of buttons on the right.

The workflow begins when a file is opened (via button, menu/shortcut, or drag-and-drop onto the window).  The preview populates with the input image, scaled to fit the preview.  The preview maintains the aspect ratio of the image, and shows transparent areas with a checkerboard pattern.

The buttons on the right become active, and pressing one of the buttons performs the corresponding operation, updating the preview.  An "undo" button undoes the last operation; undo is multi-level (bounded by a memory cap), with no redo.  A "save" button saves the modified image to disk.  The user is prompted before discarding unsaved changes (closing, quitting, or opening another file).

Input images are in common web formats (JPEG, PNG, WEBP).  All output images are saved in PNG format with transparency, including DPI metadata for printing.

## Operations

Operations may require parameters.  A dialog should open when selecting an operation to confirm the parameters.  If the operation has been run before, the previous run's parameters should be pre-populated; these are persisted across application restarts.  Long-running operations run in the background and can be cancelled.

The operations include:

- Background removal - performs an algorithmic operation that replaces the background of the image with transparency.  The foreground and background may touch zero or more edges of the image.  Two modes are offered: color-key/flood-fill (auto-detected or user-picked background color, tolerance, contiguous or global) and GrabCut segmentation.
- Background removal (AI) - similar to above, but uses an AI model.  Pluggable providers:
  - Local (rembg) - runs offline on-device; models download on first use.
  - Generic HTTP endpoint - POST the image, receive a PNG (e.g. remove.bg, rembg-server).
  - OpenAI-compatible `/v1/images/edits` endpoint.
  API keys are stored in the OS keychain.
- Extend canvas - expand the overall image area, maintaining the current image contents in the center of the image.  No scaling or cropping occurs; there is just more empty space around the existing image.  The new area is filled with transparency.
- Border - Find the edges of the image (where the image and transparency meet), and add a border of a given size and color.  Dialog options: outer outline only (fill holes), merge separate pieces into one outline, smooth/rounded outline, solid alpha (no semi-transparency), and auto-extend the canvas so the border is never clipped.
- Trim - crop away transparent padding around the content, with an optional margin.
- Resize / print size - set physical print size and DPI, with or without resampling.

## Application details

The application primarily runs on MacOS (Apple Silicon, recent versions only).  Support for Windows 11 x86 is a medium priority roadmap item; code should remain portable (no macOS-only APIs).

Technology: Python 3.12 + PySide6 (Qt), numpy/OpenCV/Pillow for image processing, rembg for local AI, managed with uv, packaged as an unsigned `.app`/`.dmg` via PyInstaller.

## Misc requirements

If any specific build process/tools are required, document that.  Setup and building should be as automated as possible.

The project is tracked in git, with unit tests (pytest) and CI (GitHub Actions).  See `PLAN.md` for the implementation plan.
