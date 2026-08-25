#!/bin/bash
# Finding an existing Slack Alfred install, so a second run of install.sh
# updates what's already there instead of quietly creating a rival copy.
#
# Sourced by install.sh (from the freshly downloaded tarball) and setup.sh.

default_install_dir() {
    echo "$HOME/.local/share/slack-alfred"
}

# Print the directory of the install currently wired up, or nothing.
# The config symlink is the authority: it is what the Alfred workflow reads
# through, so whatever it points at *is* the live install, dev checkout or not.
detect_install() {
    local config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/slack-alfred"
    local link="$config_dir/config.json"
    local dir=""

    if [ -L "$link" ]; then
        local target
        target="$(readlink "$link")"
        [[ "$target" = /* ]] || target="$config_dir/$target"
        dir="$(dirname "$target")"
        # A checkout that has since been deleted or moved: not an install.
        [ -f "$dir/setup.sh" ] || dir=""
    fi

    if [ -z "$dir" ] && [ -f "$(default_install_dir)/setup.sh" ]; then
        dir="$(default_install_dir)"
    fi

    [ -n "$dir" ] && printf '%s\n' "$dir"
}

# "dev" for a git checkout the user maintains, "managed" for a copy we
# downloaded. Only a managed install is ever overwritten or deleted.
install_kind() {
    if [ -d "$1/.git" ]; then
        echo "dev"
    else
        echo "managed"
    fi
}

# True when a config file already holds a real token.
has_token() {
    [ -f "$1" ] || return 1
    python3 - "$1" <<'PY'
import json, sys
try:
    with open(sys.argv[1]) as f:
        token = json.load(f).get("token", "")
except (OSError, ValueError):
    sys.exit(1)
sys.exit(0 if token.startswith("xoxp-") and "YOUR-TOKEN-HERE" not in token else 1)
PY
}
