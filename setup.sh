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

# ── Step 3: Write config ──────────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}Step 3${RESET}  Writing config file"
echo ""

# Write token into config.json in the repo (build.sh will symlink it)
sed "s/xoxp-YOUR-TOKEN-HERE/$token/" "$SCRIPT_DIR/config.example.json" > "$CONFIG_FILE"

echo -e "  ${GREEN}✓${RESET}  Config written to ${BOLD}config.json${RESET}"
echo ""

# ── Step 4: Build and install ────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}Step 4${RESET}  Building and installing the Alfred workflow"
echo ""

bash "$SCRIPT_DIR/build.sh"

echo -e "${GREEN}${BOLD}All done!${RESET}"
echo ""
echo -e "  Type ${BOLD}slacks${RESET} in Alfred to set your status."
echo -e "  Type ${BOLD}slackp${RESET} in Alfred to set your presence (active/away)."
echo -e "  Type a custom status and use ${BOLD}⌘↩${RESET} to save it as a preset."
echo -e "  Tab any preset to set expiry or remove it."
echo ""
