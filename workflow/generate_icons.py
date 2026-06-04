#!/usr/bin/env python3
"""Pre-generate emoji icon PNGs into the cache so the Script Filter starts instantly.
Called by build.sh — not needed at workflow runtime."""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from filter import DEFAULT_STATUSES, ICON_CACHE, CONFIG_FILE, _JXA

EXTRA = ["⚙️", "💬", "➕", "⏲️", "❌", "🟢", "⏸️"]


def generate(emoji_char):
    name = "_".join(f"{ord(c):04X}" for c in emoji_char if ord(c) > 31)
    path = os.path.join(ICON_CACHE, f"{name}.png")
    if os.path.exists(path):
        return path
    os.makedirs(ICON_CACHE, exist_ok=True)
    jxa = _JXA.replace("EMOJI", json.dumps(emoji_char)).replace("OUTPATH", json.dumps(path))
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", jxa], capture_output=True)
    return path if r.returncode == 0 and os.path.exists(path) else None


def main():
    seen = set()
    queue = []  # (emoji, label)

    def enqueue(emoji, label):
        if emoji and emoji not in seen:
            seen.add(emoji)
            queue.append((emoji, label))

    for s in DEFAULT_STATUSES:
        enqueue(s.get("icon", ""), "default")
    for e in EXTRA:
        enqueue(e, "built-in")

    # Read user config and pick up any custom status icons
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        for s in config.get("statuses", []):
            enqueue(s.get("icon", ""), "custom")
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    print("Pre-generating icons…")
    for emoji, label in queue:
        p = generate(emoji)
        tag = f" ({label})" if label != "default" else ""
        print(f"  {'✓' if p else '✗'}  {emoji}{tag}")


if __name__ == "__main__":
    main()
