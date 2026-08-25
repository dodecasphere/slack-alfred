#!/bin/bash
# Removes the Slack Alfred install: scheduler, symlinks, and the downloaded
# copy. A git checkout is never deleted — it is only unlinked.
#
#   ./uninstall.sh                # remove everything, token included
#   ./uninstall.sh --keep-token   # leave config.json behind so a reinstall reuses it
set -euo pipefail

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
RESET='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/slack-alfred"
LABEL="com.michaeldulle.slack-alfred.scheduler"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

KEEP_TOKEN=false
[ "${1:-}" = "--keep-token" ] && KEEP_TOKEN=true

# shellcheck source=tools/detect_install.sh
source "$SCRIPT_DIR/tools/detect_install.sh"

INSTALL="$(detect_install || true)"

echo ""
if [ -z "$INSTALL" ]; then
    echo -e "  Nothing installed — nothing to remove."
else
    KIND="$(install_kind "$INSTALL")"

    # Save the token before the symlink it lives behind goes away. Left as a
    # real file, which build.sh migrates into the next install.
    if [ "$KEEP_TOKEN" = true ] && [ -f "$CONFIG_DIR/config.json" ]; then
        SAVED="$(mktemp)"
        cp "$CONFIG_DIR/config.json" "$SAVED"
    fi

    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || \
        launchctl unload -w "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo -e "  ${GREEN}✓${RESET}  Scheduler stopped"

    rm -f "$CONFIG_DIR/config.json" "$CONFIG_DIR/icons"
    echo -e "  ${GREEN}✓${RESET}  Links removed"

    if [ "$KIND" = "dev" ]; then
        echo -e "  ${DIM}Left your checkout at $INSTALL untouched.${RESET}"
    else
        rm -rf "$INSTALL"
        echo -e "  ${GREEN}✓${RESET}  Removed $INSTALL"
    fi

    if [ "${SAVED:-}" != "" ]; then
        mkdir -p "$CONFIG_DIR"
        mv "$SAVED" "$CONFIG_DIR/config.json"
        echo -e "  ${GREEN}✓${RESET}  Kept your token"
    fi

    echo ""
    echo -e "  ${BOLD}One manual step:${RESET} delete the workflow in Alfred"
    echo -e "  ${DIM}(Alfred Preferences → Workflows → right-click → Delete).${RESET}"
fi
echo ""
