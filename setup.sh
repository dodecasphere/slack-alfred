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

# ── Step 1: Create a Slack app ───────────────────────────────────────────────
echo -e "${CYAN}${BOLD}Step 1${RESET}  Create a Slack app"
echo ""
echo -e "  1. We'll open https://api.slack.com/apps in your browser."
echo -e "  2. Click ${BOLD}Create New App${RESET} → ${BOLD}From scratch${RESET}."
echo -e "  3. Give it any name (e.g. \"Status Setter\") and pick your workspace."
echo ""
read -rp "$(echo -e "  ${DIM}Press Enter to open the page…${RESET}")"
open "https://api.slack.com/apps"
echo ""

# ── Step 2: Add the required scope ───────────────────────────────────────────
echo -e "${CYAN}${BOLD}Step 2${RESET}  Add the required permission scopes"
echo ""
echo -e "  In your new app:"
echo -e "  1. Go to ${BOLD}OAuth & Permissions${RESET} in the left sidebar."
echo -e "  2. Scroll to ${BOLD}User Token Scopes${RESET}."
echo -e "  3. Click ${BOLD}Add an OAuth Scope${RESET} and add all four of these scopes:"
echo -e "       ${BOLD}users.profile:write${RESET}  — set your status"
echo -e "       ${BOLD}users.profile:read${RESET}   — show your current status"
echo -e "       ${BOLD}users:write${RESET}          — set your presence (active/away)"
echo -e "       ${BOLD}emoji:read${RESET}           — suggest your workspace's custom emoji"
echo ""
read -rp "$(echo -e "  ${DIM}Press Enter once you've added the scopes…${RESET}")"
echo ""

# ── Step 3: Install and copy the token ───────────────────────────────────────
echo -e "${CYAN}${BOLD}Step 3${RESET}  Install the app and copy your token"
echo ""
echo -e "  1. Scroll back up on the same page and click ${BOLD}Install to Workspace${RESET}."
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

# ── Step 4: Write config ──────────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}Step 4${RESET}  Writing config file"
echo ""

# Write token into config.json in the repo (build.sh will symlink it)
sed "s/xoxp-YOUR-TOKEN-HERE/$token/" "$SCRIPT_DIR/config.example.json" > "$CONFIG_FILE"

echo -e "  ${GREEN}✓${RESET}  Config written to ${BOLD}config.json${RESET}"
echo ""

# ── Step 5: Build and install ────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}Step 5${RESET}  Building and installing the Alfred workflow"
echo ""

bash "$SCRIPT_DIR/build.sh"

echo -e "${GREEN}${BOLD}All done!${RESET}"
echo ""
echo -e "  Type ${BOLD}slacks${RESET} in Alfred to set your status."
echo -e "  Type ${BOLD}slackp${RESET} in Alfred to set your presence (active/away)."
echo -e "  Type a custom status and use ${BOLD}⌘↩${RESET} to save it as a preset."
echo -e "  Tab any preset to set expiry or remove it."
echo ""
