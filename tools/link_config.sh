#!/bin/bash
# Wires ~/.config/slack-alfred/<name> at this install's copy of a file or dir.
#
# Sourced by build.sh. Lives here (and not inline) so tests/test_link_config.py
# can exercise it directly — the second-install case below is subtle enough to
# have shipped a bug once already.

# Copy the token out of $1 into $2, but only if $2 is still the placeholder, so
# a real token is never clobbered by a fresh checkout's example config.
_migrate_token() {
    local from="$1"
    local to="$2"

    [[ "$to" == *.json ]] || return 0
    [ -f "$from" ] || return 0
    grep -q "xoxp-YOUR-TOKEN-HERE" "$to" 2>/dev/null || return 0
    grep -q "xoxp-YOUR-TOKEN-HERE" "$from" 2>/dev/null && return 0

    cp "$from" "$to"
    echo -e "  Migrated existing $(basename "$to") → this install"
}

symlink() {
    local target="$1"
    local link="$2"

    if [ -L "$link" ]; then
        local current
        current="$(readlink "$link")"
        # Already ours — nothing to do.
        [ "$current" = "$target" ] && return
        # A link from an older install: setup.sh just wrote the token into
        # $target, but the workflow reads through $link, so it would keep using
        # the old checkout's config. Carry the token over and repoint.
        _migrate_token "$current" "$target"
        rm "$link"
        ln -s "$target" "$link"
        echo -e "  Repointed $(basename "$link") → this install"
        return
    fi

    if [ -e "$link" ]; then
        _migrate_token "$link" "$target"
        mv "$link" "${link}.bak"
        echo -e "  Backed up existing $(basename "$link")"
    fi

    ln -s "$target" "$link"
}
