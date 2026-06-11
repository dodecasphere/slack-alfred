#!/bin/bash
set -euo pipefail

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
RESET='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/.config/slack-alfred"
OUTPUT="$SCRIPT_DIR/slack-status.alfredworkflow"

echo ""
echo -e "${BOLD}Slack Status — Alfred Workflow${RESET}"
echo -e "${DIM}──────────────────────────────${RESET}"
echo ""

# ── Python preflight ────────────────────────────────────────────────────────────
# macOS does not ship a working Python 3 by default — /usr/bin/python3 is a stub
# that only works once Xcode Command Line Tools are installed. Resolve a real one
# (Homebrew or CLT) and reuse it everywhere, including the scheduler LaunchAgent,
# so the PATH-resolved interpreter and the launchd interpreter never diverge.
PYTHON="$(command -v python3 || true)"
if [ -z "$PYTHON" ] || ! "$PYTHON" -c 'import sys' >/dev/null 2>&1; then
    echo -e "${RED}${BOLD}Python 3 not found.${RESET}"
    echo -e "  This workflow needs a working Python 3. Install it with either:"
    echo -e "    ${BOLD}xcode-select --install${RESET}   ${DIM}(Apple Command Line Tools)${RESET}"
    echo -e "    ${BOLD}brew install python3${RESET}      ${DIM}(Homebrew)${RESET}"
    echo -e "  then re-run this script."
    exit 1
fi
echo -e "${CYAN}${BOLD}Python${RESET}   Using $PYTHON"
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
"$PYTHON" "$SCRIPT_DIR/workflow/generate_emoji_list.py"
echo ""

# ── Icons ─────────────────────────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}Icons${RESET}"
"$PYTHON" "$SCRIPT_DIR/workflow/generate_icons.py"
echo ""

# ── Build ─────────────────────────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}Build${RESET}"
cd "$SCRIPT_DIR/workflow"
# Pre-compile with hash-based invalidation so .pyc survives zip/unzip mtime changes
"$PYTHON" -c "
import py_compile, glob
mode = py_compile.PycInvalidationMode.CHECKED_HASH
for src in glob.glob('*.py'):
    try: py_compile.compile(src, invalidation_mode=mode, quiet=1)
    except Exception: pass
"
zip -r "$OUTPUT" . -x "*.DS_Store" > /dev/null
echo -e "  ${GREEN}✓${RESET}  slack-status.alfredworkflow"
echo ""

# ── Scheduler (launchd) ─────────────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}Scheduler${RESET}"
LABEL="com.michaeldulle.slack-alfred.scheduler"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_NUM="$(id -u)"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT_DIR/workflow/scheduler.py</string>
    </array>
    <key>StartInterval</key>
    <integer>60</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$CONFIG_DIR/scheduler.log</string>
    <key>StandardErrorPath</key>
    <string>$CONFIG_DIR/scheduler.log</string>
</dict>
</plist>
EOF
# Reload (bootout the old one first; fall back to legacy load on older macOS).
launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
if launchctl bootstrap "gui/$UID_NUM" "$PLIST" 2>/dev/null; then
    echo -e "  ${GREEN}✓${RESET}  Loaded $LABEL (checks every 60s)"
elif launchctl load -w "$PLIST" 2>/dev/null; then
    echo -e "  ${GREEN}✓${RESET}  Loaded $LABEL (checks every 60s)"
else
    echo -e "  Could not auto-load the scheduler — load it manually:"
    echo -e "  ${DIM}launchctl bootstrap gui/$UID_NUM \"$PLIST\"${RESET}"
fi
echo ""

# ── Install ───────────────────────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}Install${RESET}"
open "$OUTPUT"
echo -e "  ${GREEN}✓${RESET}  Opening in Alfred — follow the prompt to install."
printf "  ${DIM}Nothing happened? \033]8;;file://%s\033\\⌘+click to install manually\033]8;;\033\\" "$OUTPUT"
printf "\033[0m\n"
echo ""
