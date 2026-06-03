#!/bin/bash
set -euo pipefail

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/.config/slack-alfred"
CONFIG_FILE="$CONFIG_DIR/config.json"

echo ""
echo -e "${BOLD}Slack Status — Alfred Workflow Setup${RESET}"
echo -e "${DIM}────────────────────────────────────${RESET}"
echo ""

# ── Step 1: Create a Slack app ───────────────────────────────────────────────
echo -e "${CYAN}${BOLD}Step 1${RESET}  Create a Slack app"
echo ""
echo "  1. We'll open https://api.slack.com/apps in your browser."
echo "  2. Click ${BOLD}Create New App${RESET} → ${BOLD}From scratch${RESET}."
echo "  3. Give it any name (e.g. \"Status Setter\") and pick your workspace."
echo ""
read -rp "$(echo -e "  ${DIM}Press Enter to open the page…${RESET}")"
open "https://api.slack.com/apps"
echo ""

# ── Step 2: Add the required scope ───────────────────────────────────────────
echo -e "${CYAN}${BOLD}Step 2${RESET}  Add the required permission scope"
echo ""
echo "  In your new app:"
echo "  1. Go to ${BOLD}OAuth & Permissions${RESET} in the left sidebar."
echo "  2. Scroll to ${BOLD}User Token Scopes${RESET}."
echo "  3. Click ${BOLD}Add an OAuth Scope${RESET} and add:  ${BOLD}users.profile:write${RESET}"
echo ""
read -rp "$(echo -e "  ${DIM}Press Enter once you've added the scope…${RESET}")"
echo ""

# ── Step 3: Install and copy the token ───────────────────────────────────────
echo -e "${CYAN}${BOLD}Step 3${RESET}  Install the app and copy your token"
echo ""
echo "  1. Scroll back up on the same page and click ${BOLD}Install to Workspace${RESET}."
echo "  2. Authorize the app."
echo "  3. Copy the ${BOLD}User OAuth Token${RESET} — it starts with ${BOLD}xoxp-${RESET}"
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

mkdir -p "$CONFIG_DIR"

# Copy the example config and swap in the real token
sed "s/xoxp-YOUR-TOKEN-HERE/$token/" "$SCRIPT_DIR/config.example.json" > "$CONFIG_FILE"

echo -e "  ${GREEN}✓${RESET}  Config written to ${BOLD}$CONFIG_FILE${RESET}"
echo ""
echo -e "  ${DIM}You can edit that file any time to add or change your preset statuses.${RESET}"
echo ""

# ── Step 5: Build the workflow ────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}Step 5${RESET}  Building the Alfred workflow"
echo ""

bash "$SCRIPT_DIR/build.sh"

echo ""

# ── Step 6: Install in Alfred ─────────────────────────────────────────────────
WORKFLOW_FILE="$SCRIPT_DIR/slack-status.alfredworkflow"
echo -e "${CYAN}${BOLD}Step 6${RESET}  Install in Alfred"
echo ""
echo "  Opening the workflow for you — Alfred will prompt you to install it."
echo ""
read -rp "$(echo -e "  ${DIM}Press Enter to open the workflow…${RESET}")"
open "$WORKFLOW_FILE"

echo ""
echo -e "${GREEN}${BOLD}All done!${RESET}"
echo ""
echo -e "  Type ${BOLD}slack${RESET} in Alfred to set your status."
echo -e "  Edit ${BOLD}~/.config/slack-alfred/config.json${RESET} to customize your presets."
echo ""
