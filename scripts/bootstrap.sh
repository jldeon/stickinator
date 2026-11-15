#!/usr/bin/env bash
# Install the toolchain and sync dependencies.
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found; installing it to ~/.local/bin"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

uv python install 3.12
uv python pin 3.12
uv sync

echo
echo "Ready. Try: make run"
