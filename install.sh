#!/usr/bin/env bash
# OpenCode Tools — Linux/macOS installer
# Installs all OpenCode plugin tools in one command.
#
# Usage:
#   ./install.sh
#   ./install.sh /path/to/project

set -euo pipefail

REPO="https://raw.githubusercontent.com/xxxn3m3s1sxxx/opencode-tools/main"
TOOLS="utils hashline impact verify trace rename graph changelog search lint refactor"
OPCODE_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/opencode"
PLUGIN_DIR="$OPCODE_DIR/plugins"

# Detect project root
PROJECT="${1:-}"
if [ -z "$PROJECT" ]; then
  PROJECT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi

echo ""
echo "  +------------------------------------------+"
echo "  |  OpenCode Tools Installer                |"
echo "  |  13 plugins + engines                    |"
echo "  +------------------------------------------+"
echo ""
echo "  Config:  $OPCODE_DIR"
echo "  Project: $PROJECT"
echo ""

# Create dirs
mkdir -p "$PLUGIN_DIR"

# Install plugins (.ts)
for tool in $TOOLS; do
  src="${tool}.ts"
  dst="$PLUGIN_DIR/$src"
  if [ -f "$src" ]; then
    cp "$src" "$dst"
    echo "  [plugin] $tool -> $dst (local)"
  else
    echo "  [plugin] $tool -> downloading..."
    curl -fsSL "$REPO/$src" -o "$dst" 2>/dev/null || echo "  [WARN] $tool download failed"
  fi
done

# Install to .opencode/plugins/ (project-local, auto-discovered)
LOCAL_PLUGIN_DIR="$PROJECT/.opencode/plugins"
mkdir -p "$LOCAL_PLUGIN_DIR"
for tool in $TOOLS; do
  src="${tool}.ts"
  dst="$LOCAL_PLUGIN_DIR/$src"
  if [ -f "$src" ]; then
    cp "$src" "$dst"
  elif [ ! -f "$dst" ]; then
    curl -fsSL "$REPO/$src" -o "$dst" 2>/dev/null || true
  fi
done

# Install .py to plugin dir (for plugin system)
for tool in $TOOLS; do
  [ "$tool" = "utils" ] && continue
  src="${tool}.py"
  dst="$PLUGIN_DIR/$src"
  if [ -f "$src" ]; then
    cp "$src" "$dst"
  elif [ ! -f "$dst" ]; then
    curl -fsSL "$REPO/$src" -o "$dst" 2>/dev/null || true
  fi
done

# Install engines (.py, skip utils.ts which has no .py)
for tool in $TOOLS; do
  [ "$tool" = "utils" ] && continue
  src="${tool}.py"
  dst="$PROJECT/$src"
  if [ -f "$src" ]; then
    cp "$src" "$dst"
    echo "  [engine] $tool -> $dst (local)"
  elif [ ! -f "$dst" ]; then
    echo "  [engine] $tool -> downloading..."
    curl -fsSL "$REPO/$src" -o "$dst" 2>/dev/null || echo "  [WARN] $tool download failed"
  else
    echo "  [engine] $tool -> $dst (exists)"
  fi
done

# Verify
echo ""
for tool in $TOOLS; do
  [ "$tool" = "utils" ] && continue
  ver=$(python3 "$PROJECT/${tool}.py" --version 2>/dev/null || python "$PROJECT/${tool}.py" --version 2>/dev/null || true)
  if [ -n "$ver" ]; then
    echo "  $ver"
  else
    echo "  [WARN] $tool: verify failed"
  fi
done

echo ""
echo "  Tools installed! Restart OpenCode to activate."
echo ""
