#!/usr/bin/env bash
# Build the unsigned macOS app bundle and disk image.
set -euo pipefail

cd "$(dirname "$0")/.."

APP="dist/Stickinator.app"
DMG="dist/Stickinator.dmg"

rm -rf build dist

uv run pyinstaller packaging/stickinator.spec --noconfirm --clean

# Unsigned builds get a fresh identity on every rebuild. Ad-hoc signing at
# least keeps the bundle internally consistent.
codesign --force --deep --sign - "$APP"

hdiutil create -volname "Stickinator" -srcfolder "$APP" -ov -format UDZO "$DMG"

echo "Built $APP and $DMG"
