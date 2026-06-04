#!/bin/bash
set -euo pipefail

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
RESET='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/.config/slack-alfred"
OUTPUT="$SCRIPT_DIR/slack-status.alfredworkflow"

echo ""
echo -e "${BOLD}Slack Status — Alfred Workflow${RESET}"
echo -e "${DIM}──────────────────────────────${RESET}"
echo ""

# ── Config ────────────────────────────────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/config.json" ]; then
    cp "$SCRIPT_DIR/config.example.json" "$SCRIPT_DIR/config.json"
    echo -e "${CYAN}${BOLD}Config${RESET}   Created config.json — add your Slack token before using."
    echo ""
fi

# ── Symlinks ──────────────────────────────────────────────────────────────────
mkdir -p "$CONFIG_DIR"
mkdir -p "$SCRIPT_DIR/icons"

symlink() {
    local target="$1"
    local link="$2"

    if [ -L "$link" ]; then
        return
    fi
    if [ -e "$link" ]; then
        if [[ "$link" == *.json ]] && grep -q "xoxp-YOUR-TOKEN-HERE" "$target" 2>/dev/null; then
            cp "$link" "$target"
            echo -e "  Migrated existing $(basename "$link") → repo"
        fi
        mv "$link" "${link}.bak"
        echo -e "  Backed up existing $(basename "$link")"
    fi
    ln -s "$target" "$link"
}

symlink "$SCRIPT_DIR/config.json" "$CONFIG_DIR/config.json"
symlink "$SCRIPT_DIR/icons"       "$CONFIG_DIR/icons"

# ── Emoji list ────────────────────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}Emoji${RESET}"
python3 "$SCRIPT_DIR/workflow/generate_emoji_list.py"
echo ""

# ── Icons ─────────────────────────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}Icons${RESET}"
python3 "$SCRIPT_DIR/workflow/generate_icons.py"
echo ""

# ── Build ─────────────────────────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}Build${RESET}"
cd "$SCRIPT_DIR/workflow"
zip -r "$OUTPUT" . -x "*.DS_Store" -x "__pycache__/*" -x "*.pyc" > /dev/null
echo -e "  ${GREEN}✓${RESET}  slack-status.alfredworkflow"
echo ""

# ── Install ───────────────────────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}Install${RESET}"
open "$OUTPUT"
echo -e "  ${GREEN}✓${RESET}  Opening in Alfred — follow the prompt to install."
printf "  ${DIM}Nothing happened? \033]8;;file://%s\033\\⌘+click to install manually\033]8;;\033\\" "$OUTPUT"
printf "\033[0m\n"
echo ""
