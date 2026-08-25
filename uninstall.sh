#!/bin/bash
# Removes the Slack Alfred install: scheduler, symlinks, and the downloaded
# copy. A git checkout is never deleted — it is only unlinked.
#
#   curl -fsSL https://raw.githubusercontent.com/dodecasphere/slack-alfred/main/uninstall.sh | bash
#   ./uninstall.sh                # ask, then remove everything
#   ./uninstall.sh --yes          # don't ask
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
TARBALL_URL="${SLACK_ALFRED_TARBALL_URL:-https://github.com/dodecasphere/slack-alfred/archive/refs/heads/main.tar.gz}"

KEEP_TOKEN=false
ASSUME_YES=false
for arg in "$@"; do
    case "$arg" in
        --keep-token) KEEP_TOKEN=true ;;
        --yes|-y)     ASSUME_YES=true ;;
    esac
done

# Piped from curl there is no repo around us, so fetch the detection helpers.
if [ -f "$SCRIPT_DIR/tools/detect_install.sh" ]; then
    HELPERS="$SCRIPT_DIR/tools/detect_install.sh"
else
    STAGING="$(mktemp -d)"
    trap 'rm -rf "$STAGING"' EXIT
    curl -fsSL "$TARBALL_URL" | tar -xz --strip-components=1 -C "$STAGING"
    HELPERS="$STAGING/tools/detect_install.sh"
fi
# shellcheck source=tools/detect_install.sh
source "$HELPERS"

# `curl … | bash` leaves stdin on the download pipe, so the confirmation below
# would read EOF. Grab the real terminal back when there is one.
if [ ! -t 0 ]; then
    { exec < /dev/tty; } 2>/dev/null || true
fi

INSTALL="$(detect_install || true)"

echo ""
if [ -z "$INSTALL" ]; then
    echo -e "  Nothing installed — nothing to remove."
    echo ""
    exit 0
fi

KIND="$(install_kind "$INSTALL")"

echo -e "${BOLD}Uninstall Slack Alfred${RESET}"
echo ""
if [ "$KIND" = "dev" ]; then
    echo -e "  Unlinks ${BOLD}$INSTALL${RESET} ${DIM}(a git checkout — its files stay)${RESET}"
else
    echo -e "  Removes ${BOLD}$INSTALL${RESET}"
fi
echo -e "  Stops the scheduler and removes the ~/.config links"
[ "$KEEP_TOKEN" = false ] && echo -e "  ${DIM}Your token goes with it.${RESET}"
echo ""

if [ "$ASSUME_YES" = false ]; then
    read -rp "$(echo -e "  ${BOLD}Go ahead?${RESET} [y/N]: ")" answer || answer=""
    case "$answer" in
        y|Y|yes|YES) ;;
        *) echo ""; echo "  Cancelled. Nothing changed."; echo ""; exit 0 ;;
    esac
    echo ""
fi

# Save the token before the symlink it lives behind goes away. Left as a real
# file, which build.sh migrates into the next install.
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
echo ""
