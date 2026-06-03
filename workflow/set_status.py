#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import urllib.request

CONFIG_FILE = os.path.expanduser("~/.config/slack-alfred/config.json")
SETUP_URL = "https://api.slack.com/apps"


def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def set_slack_status(token, text, emoji):
    payload = json.dumps({
        "profile": {
            "status_text": text,
            "status_emoji": emoji,
            "status_expiration": 0,
        }
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://slack.com/api/users.profile.set",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def do_setup():
    subprocess.run(["open", SETUP_URL])
    # AppleScript dialog with step-by-step and a "Copy config command" button
    steps = (
        "1. Create a new Slack app at api.slack.com/apps\\n"
        "2. From scratch → name it, pick your workspace\\n"
        "3. OAuth & Permissions → User Token Scopes → add: users.profile:write\\n"
        "4. Install to Workspace → copy the xoxp- token\\n"
        "5. In Terminal, run:\\n"
        "   mkdir -p ~/.config/slack-alfred\\n"
        "   cp <workflow-folder>/config.example.json ~/.config/slack-alfred/config.json\\n"
        "   # then open the file and paste your token"
    )
    cmd_text = "mkdir -p ~/.config/slack-alfred && cp config.example.json ~/.config/slack-alfred/config.json"
    script = (
        f'set btn to button returned of '
        f'(display dialog "Slack Status Setter — Setup\\n\\n{steps}" '
        f'with title "Slack Status Setup" '
        f'buttons {{"Copy config command", "OK"}} default button "OK")\\n'
        f'if btn = "Copy config command" then\\n'
        f'  set the clipboard to "{cmd_text}"\\n'
        f'end if'
    )
    subprocess.Popen(["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Opening Slack API… follow the dialog for setup steps.")


def main():
    arg = sys.argv[1].strip() if len(sys.argv) > 1 else ""

    if arg == "setup":
        do_setup()
        return

    config = load_config()
    if not config or not config.get("token"):
        print("No token configured. Run 'slack' in Alfred to set up.")
        return

    try:
        status = json.loads(arg)
    except json.JSONDecodeError:
        print(f"Bad argument: {arg!r}")
        return

    text = status.get("text", "")
    emoji = status.get("emoji", "")

    try:
        result = set_slack_status(config["token"], text, emoji)
    except Exception as e:
        print(f"Request failed: {e}")
        return

    if result.get("ok"):
        print("Status cleared" if not text else f"Status set: {emoji} {text}".strip())
    else:
        print(f"Slack error: {result.get('error', 'unknown')}")


if __name__ == "__main__":
    main()
