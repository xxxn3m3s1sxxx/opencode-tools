#!/bin/sh
# OpenCode Tools — Combined installer
#
# Installs all OpenCode tools (hashline, impact) in one command.
# Auto-detects OpenCode config dir, project root, and Python.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/xxxn3m3s1sxxx/opencode-tools/main/install.sh | sh
#   ./install.sh
#   ./install.sh /path/to/project

set -e

REPO_BASE="https://raw.githubusercontent.com/xxxn3m3s1sxxx/opencode-tools/main"

# --- Detect OpenCode config dir ---
if [ -n "$XDG_CONFIG_HOME" ]; then
    OPCODE_DIR="$XDG_CONFIG_HOME/opencode"
elif [ -n "$HOME" ]; then
    OPCODE_DIR="$HOME/.config/opencode"
elif [ -n "$USERPROFILE" ]; then
    OPCODE_DIR="$USERPROFILE/.config/opencode"
else
    OPCODE_DIR="${HOME:-$HOME}/.config/opencode"
fi

# --- Detect project root ---
if [ -n "$1" ]; then
    PROJECT="$1"
else
    PROJECT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
fi

# --- Detect script source dir ---
SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo "")"

echo ""
echo "  +------------------------------------------+"
echo "  |  OpenCode Tools Installer                |"
echo "  |  hashline + impact + verify + trace      |"
echo "  +------------------------------------------+"
echo ""
echo "  Config: $OPCODE_DIR"
echo "  Project: $PROJECT"
echo ""

# --- Helpers ---
TOOLS="hashline impact verify trace"

install_file() {
    local src="$1"
    local dest="$2"
    local name="$3"
    local tool="$4"
    if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/$tool/$src" ]; then
        cp "$SCRIPT_DIR/$tool/$src" "$dest"
        echo "    $name -> $dest (local)"
        return 0
    fi
    if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/$src" ]; then
        cp "$SCRIPT_DIR/$src" "$dest"
        echo "    $name -> $dest (local)"
        return 0
    fi
    if command -v curl >/dev/null 2>&1; then
        curl -fsSLo "$dest" "$REPO_BASE/$src" && {
            echo "    $name -> $dest (downloaded)"
            return 0
        }
    fi
    echo "    SKIP $name (not found, no curl)"
    return 1
}

# --- Install plugins ---
PLUGIN_DIR="$OPCODE_DIR/plugins"
mkdir -p "$PLUGIN_DIR"

for tool in $TOOLS; do
    echo "  [$tool] plugin..."
    install_file "$tool.ts" "$PLUGIN_DIR/$tool.ts" "Plugin" "$tool"
done

# --- Install engines ---
for tool in $TOOLS; do
    ENGINE_DEST="$PROJECT/$tool.py"
    if [ -f "$ENGINE_DEST" ]; then
        echo "  [$tool] engine -> $ENGINE_DEST (exists)"
    else
        echo "  [$tool] engine..."
        install_file "$tool.py" "$ENGINE_DEST" "Engine" "$tool"
    fi
done

# --- Verify ---
echo ""
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PYTHON="$cmd"
        break
    fi
done

if [ -n "$PYTHON" ]; then
    for tool in $TOOLS; do
        ENGINE="$PROJECT/$tool.py"
        if [ -f "$ENGINE" ]; then
            V=$("$PYTHON" "$ENGINE" --version 2>/dev/null) && \
                echo "  $tool: $V" || \
                echo "  $tool: engine exists but verify failed"
        fi
    done
else
    echo "  Python not found in PATH"
fi

# --- Done ---
echo ""
echo "  Tools installed! Restart OpenCode to activate."
echo ""
echo "  Installed: hashline (stable) + impact + verify + trace"
echo ""
echo "  Test:"
echo "    python $PROJECT/hashline.py --version"
echo "    python $PROJECT/impact.py --version"
echo "    python $PROJECT/verify.py --version"
echo "    python $PROJECT/trace.py --version"
echo "    python $PROJECT/test_hashline.py"
echo ""
