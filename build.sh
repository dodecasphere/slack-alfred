#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="$SCRIPT_DIR/slack-status.alfredworkflow"
cd "$SCRIPT_DIR/workflow"
zip -r "$OUTPUT" . -x "*.DS_Store" -x "__pycache__/*" -x "*.pyc" > /dev/null
echo "Built: slack-status.alfredworkflow"
echo "Double-click the file to install in Alfred."
