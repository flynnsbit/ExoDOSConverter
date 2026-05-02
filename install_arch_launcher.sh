#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_FILE="$DESKTOP_DIR/exodosconverter.desktop"
LAUNCHER="$SCRIPT_DIR/launch_exodosconverter.sh"
ICON_FILE="$SCRIPT_DIR/exodosicon.ico"

if [[ ! -f "$LAUNCHER" ]]; then
    echo "Launcher script not found: $LAUNCHER" >&2
    exit 1
fi

mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=ExoDOSConverter
Comment=Convert eXo collections
Exec=$LAUNCHER
Path=$SCRIPT_DIR
Icon=$ICON_FILE
Terminal=false
Categories=Game;Utility;
StartupNotify=true
EOF

chmod +x "$LAUNCHER" "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo "Installed desktop launcher: $DESKTOP_FILE"
