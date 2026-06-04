#!/usr/bin/env python3
"""
Fetches custom workspace emoji from Slack's emoji.list API and writes
~/.config/slack-alfred/custom_emoji.json. Invoked asynchronously by
filter_status.py when the cache is missing or stale.
Requires the emoji:read scope on the Slack app token.
"""
import json
import os
import time
import urllib.request

CONFIG_FILE        = os.path.expanduser("~/.config/slack-alfred/config.json")
CUSTOM_EMOJI_CACHE = os.path.expanduser("~/.config/slack-alfred/custom_emoji.json")


def main():
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        token = config.get("token", "")
    except Exception:
        return

    if not token:
        return

    req = urllib.request.Request(
        "https://slack.com/api/emoji.list",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except Exception:
        return

    if not data.get("ok"):
        return

    # Exclude aliases — keep only directly-defined custom emoji
    emoji = {k: v for k, v in data.get("emoji", {}).items()
             if not v.startswith("alias:")}

    os.makedirs(os.path.dirname(CUSTOM_EMOJI_CACHE), exist_ok=True)
    with open(CUSTOM_EMOJI_CACHE, "w") as f:
        json.dump({"fetched_at": int(time.time()), "emoji": emoji},
                  f, ensure_ascii=False)


if __name__ == "__main__":
    main()
