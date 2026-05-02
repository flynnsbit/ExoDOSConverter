#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"
REQ_HASH_FILE="$VENV_DIR/.requirements.sha256"

cd "$SCRIPT_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
    python3 -m venv "$VENV_DIR"
fi

if [[ ! -f "$REQUIREMENTS_FILE" ]]; then
    echo "Missing requirements file: $REQUIREMENTS_FILE" >&2
    exit 1
fi

CURRENT_REQ_HASH="$(sha256sum "$REQUIREMENTS_FILE" | awk '{print $1}')"
STRICT_MARKER="strict:$CURRENT_REQ_HASH"
FALLBACK_MARKER="fallback:$CURRENT_REQ_HASH"
INSTALLED_REQ_HASH=""
if [[ -f "$REQ_HASH_FILE" ]]; then
    INSTALLED_REQ_HASH="$(cat "$REQ_HASH_FILE")"
fi

if [[ "$INSTALLED_REQ_HASH" != "$STRICT_MARKER" && "$INSTALLED_REQ_HASH" != "$FALLBACK_MARKER" ]]; then
    if "$PIP_BIN" install -r "$REQUIREMENTS_FILE"; then
        echo "$STRICT_MARKER" > "$REQ_HASH_FILE"
    else
        echo "Falling back to compatible dependency versions for this Python runtime..."
        "$PIP_BIN" install requests chardet pillow
        echo "$FALLBACK_MARKER" > "$REQ_HASH_FILE"
    fi
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/main.py"
