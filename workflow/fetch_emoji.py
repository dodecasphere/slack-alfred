#!/usr/bin/env python3
"""
Fetches custom workspace emoji from Slack's emoji.list API, writes
~/.config/slack-alfred/custom_emoji.json, and downloads each image to
the icon cache. Creates custom_emoji_images.done after images finish.
Invoked asynchronously by filter_status.py when cache or images are
missing or stale. Requires the emoji:read scope on the token.
"""
import json
import os
import time
import urllib.parse
import urllib.request

CONFIG_FILE               = os.path.expanduser("~/.config/slack-alfred/config.json")
CUSTOM_EMOJI_CACHE        = os.path.expanduser("~/.config/slack-alfred/custom_emoji.json")
CUSTOM_EMOJI_IMAGES_DONE  = os.path.expanduser("~/.config/slack-alfred/custom_emoji_images.done")
ICON_CACHE                = os.path.expanduser("~/.config/slack-alfred/icons")


def _download_images(emoji_dict):
    os.makedirs(ICON_CACHE, exist_ok=True)
    for name, url in emoji_dict.items():
        ext  = os.path.splitext(urllib.parse.urlparse(url).path)[1] or ".png"
        dest = os.path.join(ICON_CACHE, f"{name}{ext}")
        if os.path.exists(dest):
            continue
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                with open(dest, "wb") as f:
                    f.write(r.read())
        except Exception:
            pass


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

    _download_images(emoji)

    # Mark images as complete so filter_status.py stops re-triggering fetches
    open(CUSTOM_EMOJI_IMAGES_DONE, "w").close()


if __name__ == "__main__":
    main()
