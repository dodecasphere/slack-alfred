#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/.config/slack-alfred"
OUTPUT="$SCRIPT_DIR/slack-status.alfredworkflow"

# ── Config ────────────────────────────────────────────────────────────────────
# Create config.json in the repo from the example if it doesn't exist yet
if [ ! -f "$SCRIPT_DIR/config.json" ]; then
    cp "$SCRIPT_DIR/config.example.json" "$SCRIPT_DIR/config.json"
    echo "Created config.json — add your Slack token before using."
fi

# ── Symlinks ──────────────────────────────────────────────────────────────────
mkdir -p "$CONFIG_DIR"
mkdir -p "$SCRIPT_DIR/icons"

symlink() {
    local target="$1"   # file/dir in the repo
    local link="$2"     # path under ~/.config/slack-alfred

    if [ -L "$link" ]; then
        return  # already a symlink, leave it alone
    fi
    if [ -e "$link" ]; then
        # Real file/dir exists — for config, migrate the token first
        if [[ "$link" == *.json ]] && grep -q "xoxp-YOUR-TOKEN-HERE" "$target" 2>/dev/null; then
            cp "$link" "$target"
            echo "  Migrated existing $(basename "$link") → repo"
        fi
        mv "$link" "${link}.bak"
        echo "  Backed up existing $(basename "$link")"
    fi
    ln -s "$target" "$link"
    echo "  Linked: $(basename "$link") → $target"
}

echo "Setting up symlinks…"
symlink "$SCRIPT_DIR/config.json" "$CONFIG_DIR/config.json"
symlink "$SCRIPT_DIR/icons"       "$CONFIG_DIR/icons"
echo ""

# ── Build ─────────────────────────────────────────────────────────────────────
echo "Building workflow…"
cd "$SCRIPT_DIR/workflow"
zip -r "$OUTPUT" . -x "*.DS_Store" -x "__pycache__/*" -x "*.pyc" > /dev/null
echo "Built: slack-status.alfredworkflow"
echo "Double-click the file to install in Alfred."
