#!/bin/bash
set -euo pipefail

INSTALL_DIR="$HOME/.local/share/slack-alfred"
TARBALL_URL="https://github.com/dodecasphere/slack-alfred/archive/refs/heads/main.tar.gz"

echo ""
echo "Downloading Slack Alfred…"
mkdir -p "$INSTALL_DIR"
curl -fsSL "$TARBALL_URL" | tar -xz --strip-components=1 -C "$INSTALL_DIR"

bash "$INSTALL_DIR/setup.sh"
