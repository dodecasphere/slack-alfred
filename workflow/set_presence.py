#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import urllib.request

CONFIG_FILE = os.path.expanduser("~/.config/slack-alfred/config.json")


def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def notify_error(detail=""):
    script = f'display notification {json.dumps(detail)} with title "❌ Slack presence not set"'
    subprocess.Popen(["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    presence = sys.stdin.read().strip()

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
        print("🧑‍💻  Active" if presence == "auto" else "🏃  Away")
    else:
        error = result.get("error", "unknown")
        if error == "missing_scope":
            notify_error("Add users:write scope to your Slack app — see README")
        else:
            notify_error(f"Slack API error: {error}")


if __name__ == "__main__":
    main()
