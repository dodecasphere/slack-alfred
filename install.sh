#!/bin/bash
set -euo pipefail

TARBALL_URL="https://github.com/dodecasphere/slack-alfred/archive/refs/heads/main.tar.gz"

BOLD='\033[1m'
DIM='\033[2m'
CYAN='\033[0;36m'
RED='\033[0;31m'
RESET='\033[0m'

# `curl … | bash` leaves stdin on the download pipe, so the menu below would
# read EOF and never prompt. Grab the real terminal back.
if [ ! -t 0 ]; then
    { exec < /dev/tty; } 2>/dev/null || true
fi

# Download first, into a staging dir: the detection helpers live in the repo so
# they can be tested, and nothing is committed to disk until the user chooses.
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT

echo ""
echo "Downloading Slack Alfred…"
curl -fsSL "$TARBALL_URL" | tar -xz --strip-components=1 -C "$STAGING"

# shellcheck source=tools/detect_install.sh
source "$STAGING/tools/detect_install.sh"

INSTALL_DIR="$(default_install_dir)"
EXISTING="$(detect_install || true)"
FRESH=false

if [ -n "$EXISTING" ]; then
    KIND="$(install_kind "$EXISTING")"
    echo ""
    echo -e "${CYAN}${BOLD}Found an existing install${RESET}"
    if [ "$KIND" = "dev" ]; then
        echo -e "  ${BOLD}$EXISTING${RESET} ${DIM}(a git checkout — we won't touch its files)${RESET}"
    else
        echo -e "  ${BOLD}$EXISTING${RESET}"
    fi
    echo ""
    echo -e "  ${BOLD}1${RESET}  Update it            ${DIM}(keeps your token and presets)${RESET}"
    echo -e "  ${BOLD}2${RESET}  Remove it and start fresh"
    echo -e "  ${BOLD}3${RESET}  Cancel"
    echo ""
    read -rp "$(echo -e "  ${DIM}Choose [1]: ${RESET}")" choice
    choice="${choice:-1}"
    echo ""

    case "$choice" in
        1)
            if [ "$KIND" = "dev" ]; then
                # Never overwrite a checkout the user maintains — just re-run it.
                echo -e "  Using your checkout as-is. ${DIM}Run 'git pull' there for the latest.${RESET}"
                INSTALL_DIR="$EXISTING"
            else
                INSTALL_DIR="$EXISTING"
                cp -R "$STAGING/." "$INSTALL_DIR/"
            fi
            ;;
        2)
            if [ "$KIND" = "dev" ]; then
                echo -e "  ${RED}That's a git checkout — we won't delete it.${RESET}"
                echo -e "  Unlinking it instead; the files stay where they are."
            fi
            bash "$STAGING/uninstall.sh" --keep-token
            FRESH=true
            ;;
        *)
            echo "  Cancelled. Nothing changed."
            exit 0
            ;;
    esac
fi

if [ -z "$EXISTING" ] || [ "$FRESH" = true ]; then
    mkdir -p "$INSTALL_DIR"
    cp -R "$STAGING/." "$INSTALL_DIR/"
fi

bash "$INSTALL_DIR/setup.sh"
