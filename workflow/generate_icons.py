#!/usr/bin/env python3
"""Pre-generate emoji icon PNGs into the cache so the Script Filter starts instantly.
Called by build.sh — not needed at workflow runtime."""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from filter import DEFAULT_STATUSES, ICON_CACHE, _JXA

# Icons used by filter.py outside of DEFAULT_STATUSES
EXTRA = ["⚙️", "💬", "➕"]


def generate(emoji_char):
    name = "_".join(f"{ord(c):04X}" for c in emoji_char if ord(c) > 31)
    path = os.path.join(ICON_CACHE, f"{name}.png")
    if os.path.exists(path):
        return path  # already cached
    os.makedirs(ICON_CACHE, exist_ok=True)
    jxa = _JXA.replace("EMOJI", json.dumps(emoji_char)).replace("OUTPATH", json.dumps(path))
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", jxa], capture_output=True)
    return path if r.returncode == 0 and os.path.exists(path) else None


def main():
    all_emoji = [s["icon"] for s in DEFAULT_STATUSES if s.get("icon")] + EXTRA
    print("Pre-generating icons…")
    for emoji in all_emoji:
        p = generate(emoji)
        print(f"  {'✓' if p else '✗'}  {emoji}")


if __name__ == "__main__":
    main()
