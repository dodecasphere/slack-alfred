#!/bin/bash
set -euo pipefail

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
RESET='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.json"

# ── Reattach to the terminal ─────────────────────────────────────────────────
# `curl … | bash` leaves stdin pointing at the download pipe, so a `read` would
# hit EOF instantly and the script would die mid-walkthrough with no prompt and
# no error. Called only on the paths that actually prompt, so a re-run with a
# token already configured stays fully non-interactive.
require_terminal() {
    [ -t 0 ] && return 0
    if ! exec < /dev/tty; then
        echo "setup.sh needs a terminal for the interactive walkthrough." >&2
        echo "Run it directly: bash $SCRIPT_DIR/setup.sh" >&2
        exit 1
    fi
}

echo ""
echo -e "${BOLD}Slack Status — Alfred Workflow Setup${RESET}"
echo -e "${DIM}────────────────────────────────────${RESET}"
echo ""

# ── Preflight: Python 3 ──────────────────────────────────────────────────────
# macOS ships no working Python 3 by default. Fail fast here, before the Slack
# app walkthrough, rather than partway through build.sh.
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys' >/dev/null 2>&1; then
    echo -e "${RED}${BOLD}Python 3 not found.${RESET}"
    echo -e "  This workflow needs a working Python 3. Install it with either:"
    echo -e "    ${BOLD}xcode-select --install${RESET}   ${DIM}(Apple Command Line Tools)${RESET}"
    echo -e "    ${BOLD}brew install python3${RESET}      ${DIM}(Homebrew)${RESET}"
    echo -e "  then re-run this setup."
    exit 1
fi

# ── Do we already have a token? ──────────────────────────────────────────────
# Re-running the installer should be boring: keep the token that's already
# there and go straight to rebuilding. --reconfigure forces the walkthrough.
# shellcheck source=tools/detect_install.sh
source "$SCRIPT_DIR/tools/detect_install.sh"

RECONFIGURE=false
[ "${1:-}" = "--reconfigure" ] && RECONFIGURE=true

NEED_TOKEN=true
if [ "$RECONFIGURE" = false ] && has_token "$CONFIG_FILE"; then
    NEED_TOKEN=false
    echo -e "${CYAN}${BOLD}Token${RESET}    Using the one already in config.json"
    echo -e "  ${DIM}Run 'setup.sh --reconfigure' to set up a different Slack app.${RESET}"
    echo ""
fi

if [ "$NEED_TOKEN" = true ]; then
    require_terminal

    # ── Step 1: Create the Slack app from a manifest ─────────────────────────────
    # The manifest prefills the app name and all four user scopes, so there is no
    # clicking through OAuth settings. pbcopy is a fallback for the rare case where
    # the prefilled link doesn't take: paste it into "From an app manifest".
    echo -e "${CYAN}${BOLD}Step 1${RESET}  Create your Slack app"
    echo ""
    echo -e "  We'll open a prefilled link. All four permission scopes are already set:"
    echo -e "       ${BOLD}users.profile:write${RESET}  — set your status"
    echo -e "       ${BOLD}users.profile:read${RESET}   — show your current status"
    echo -e "       ${BOLD}users:write${RESET}          — set your presence (active/away)"
    echo -e "       ${BOLD}emoji:read${RESET}           — suggest your workspace's custom emoji"
    echo ""
    echo -e "  On the page: pick your workspace, then click ${BOLD}Create${RESET}."
    echo ""

    MANIFEST_FILE="$SCRIPT_DIR/slack-app-manifest.json"
    if CREATE_URL="$(python3 "$SCRIPT_DIR/tools/manifest_url.py" "$MANIFEST_FILE" 2>/dev/null)"; then
        pbcopy < "$MANIFEST_FILE" 2>/dev/null && \
            echo -e "  ${DIM}(The manifest is also on your clipboard, just in case.)${RESET}"
    else
        CREATE_URL="https://api.slack.com/apps"
        echo -e "  ${RED}Couldn't build the prefilled link — we'll open the apps page instead.${RESET}"
        echo -e "  Choose ${BOLD}From an app manifest${RESET} and paste the contents of"
        echo -e "  ${BOLD}slack-app-manifest.json${RESET}."
    fi
    echo ""
    read -rp "$(echo -e "  ${DIM}Press Enter to open the page…${RESET}")"
    open "$CREATE_URL"
    echo ""

    # ── Step 2: Install and copy the token ───────────────────────────────────────
    echo -e "${CYAN}${BOLD}Step 2${RESET}  Install the app and copy your token"
    echo ""
    echo -e "  1. Go to ${BOLD}OAuth & Permissions${RESET} and click ${BOLD}Install to Workspace${RESET}."
    echo -e "  2. Authorize the app."
    echo -e "  3. Copy the ${BOLD}User OAuth Token${RESET} — it starts with ${BOLD}xoxp-${RESET}"
    echo ""

    while true; do
      read -rp "$(echo -e "  ${BOLD}Paste your token here:${RESET} ")" token
      token="$(echo "$token" | xargs)"  # trim whitespace
      if [[ "$token" == xoxp-* ]]; then
        break
      else
        echo -e "  ${RED}That doesn't look right — it should start with xoxp-. Try again.${RESET}"
      fi
    done
    echo ""
fi

# ── Step 3: Write config ──────────────────────────────────────────────────────
if [ "$NEED_TOKEN" = true ]; then
    echo -e "${CYAN}${BOLD}Step 3${RESET}  Writing config file"
    echo ""

    # Write the token into config.json (build.sh symlinks it into ~/.config).
    # json.dump rather than sed: a token is not a safe sed replacement string.
    TOKEN="$token" python3 - "$SCRIPT_DIR/config.example.json" "$CONFIG_FILE" <<'PY'
import json, os, sys
with open(sys.argv[1]) as f:
    config = json.load(f)
config["token"] = os.environ["TOKEN"]
with open(sys.argv[2], "w") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
    f.write("\n")
PY

    echo -e "  ${GREEN}✓${RESET}  Config written to ${BOLD}config.json${RESET}"
    echo ""
fi

# ── Step 4: Build and install ────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}Step 4${RESET}  Building and installing the Alfred workflow"
echo ""

if [ "${SLACK_ALFRED_NO_BUILD:-}" = "1" ]; then
    exit 0   # test seam: skip Alfred, launchd, and the network
fi

bash "$SCRIPT_DIR/build.sh"

echo -e "${GREEN}${BOLD}All done!${RESET}"
echo ""
echo -e "  Type ${BOLD}slacks${RESET} in Alfred to set your status."
echo -e "  Type ${BOLD}slackp${RESET} in Alfred to set your presence (active/away)."
echo -e "  Type a custom status and use ${BOLD}⌘↩${RESET} to save it as a preset."
echo -e "  Tab any preset to set expiry or remove it."
echo ""
