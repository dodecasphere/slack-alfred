#!/usr/bin/env python3
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from common import write_current_status_cache

def main():
    token = sys.argv[1] if len(sys.argv) > 1 else ""
    if not token:
        return
    try:
        req = urllib.request.Request(
            "https://slack.com/api/users.profile.get",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        if not data.get("ok"):
            return
        profile = data.get("profile", {})
        write_current_status_cache(
            profile.get("status_text", ""),
            profile.get("status_emoji", ""),
            profile.get("status_expiration", 0),
        )
    except Exception:
        pass

if __name__ == "__main__":
    main()
