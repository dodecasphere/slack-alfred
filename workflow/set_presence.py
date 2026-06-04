#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from common import (TOKEN_ERROR_FLAG, _AUTH_ERRORS,
                    set_token_error_flag, clear_token_error_flag,
                    load_config, do_setup)


def notify_error(detail=""):
    script = f'display notification {json.dumps(detail)} with title "❌ Slack presence not set"'
    subprocess.Popen(["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    arg = sys.stdin.read().strip()

    if arg == "setup":
        do_setup()
        return

    try:
        data = json.loads(arg)
        if isinstance(data, dict) and data.get("action") == "save_token":
            import set_status
            set_status.save_token(data)
            return
    except (json.JSONDecodeError, TypeError):
        pass

    presence = arg
    if presence not in ("auto", "away"):
        notify_error(f"Unknown presence value: {presence!r}")
        return

    config = load_config()
    if not config or not config.get("token"):
        notify_error("No token — run 'slacks' in Alfred to set up.")
        return

    payload = json.dumps({"presence": presence}).encode("utf-8")
    req = urllib.request.Request(
        "https://slack.com/api/users.setPresence",
        data=payload,
        headers={
            "Authorization": f"Bearer {config['token']}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        notify_error(f"Request failed: {e}")
        return

    if result.get("ok"):
        clear_token_error_flag()
        print("🧑‍💻  Active" if presence == "auto" else "🏃  Away")
    else:
        error = result.get("error", "unknown")
        if error in _AUTH_ERRORS:
            set_token_error_flag()
            print("❌ Token rejected — open Alfred and Tab the warning to update")
        elif error == "missing_scope":
            notify_error("Add users:write scope to your Slack app — see README")
        else:
            notify_error(f"Slack API error: {error}")


if __name__ == "__main__":
    main()
