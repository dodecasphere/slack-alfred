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


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")


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


def notify_error(detail=""):
    script = f'display notification {json.dumps(detail)} with title "❌ Slack status not set"'
    subprocess.Popen(["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def notify_success(message):
    script = f'display notification {json.dumps(message)} with title "Slack Status"'
    subprocess.Popen(["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ask_dialog(prompt, default="", title="Slack Status", last=False):
    """Show a text-input dialog. Returns the entered string, or None if cancelled."""
    btn = "Save" if last else "Next"
    script = (
        f'set r to display dialog {json.dumps(prompt)} '
        f'default answer {json.dumps(default)} '
        f'with title {json.dumps(title)} '
        f'buttons {{"Cancel", {json.dumps(btn)}}} '
        f'default button {json.dumps(btn)}\n'
        f'return text returned of r'
    )
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def do_setup():
    subprocess.run(["open", SETUP_URL])
    steps = (
        "1. Create a new Slack app at api.slack.com/apps\\n"
        "2. From scratch → name it, pick your workspace\\n"
        "3. OAuth & Permissions → User Token Scopes → add: users.profile:write\\n"
        "4. Install to Workspace → copy the xoxp- token\\n"
        "5. Run ./setup.sh in the repo folder"
    )
    script = (
        f'display dialog "Slack Status Setter — Setup\\n\\n{steps}" '
        f'with title "Slack Status Setup" '
        f'buttons {{"OK"}} default button "OK"'
    )
    subprocess.Popen(["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def do_add_preset():
    title = ask_dialog(
        "What should this preset be called?\n(This is also the Slack status text.)",
        title="Add Preset",
    )
    if title is None:
        return

    icon = ask_dialog(
        "Icon emoji for the Alfred menu:\n(e.g. 🏋️)",
        default="💬",
        title="Add Preset",
    )
    if icon is None:
        return

    slack_emoji = ask_dialog(
        "Slack emoji code to show in your status:\n(e.g. :calendar: — leave blank for none)",
        title="Add Preset",
        last=True,
    )
    if slack_emoji is None:
        return

    config = load_config()
    if not config:
        notify_error("Couldn't read config file.")
        return

    statuses = config.get("statuses", [])
    statuses.append({
        "title": title.strip(),
        "emoji": slack_emoji.strip(),
        "text":  title.strip(),
        "icon":  icon.strip(),
    })
    config["statuses"] = statuses

    try:
        save_config(config)
    except Exception as e:
        notify_error(f"Couldn't save config: {e}")
        return

    notify_success(f'Preset added: "{title.strip()}"')


def main():
    arg = sys.stdin.read().strip()

    if arg == "setup":
        do_setup()
        return

    if arg == "add_preset":
        do_add_preset()
        return

    config = load_config()
    if not config or not config.get("token"):
        notify_error("No token configured — run 'slack' in Alfred to set up.")
        return

    try:
        status = json.loads(arg)
    except json.JSONDecodeError:
        notify_error(f"Unexpected input: {arg!r}")
        return

    text = status.get("text", "")
    emoji = status.get("emoji", "")

    try:
        result = set_slack_status(config["token"], text, emoji)
    except Exception as e:
        notify_error(f"Request failed: {e}")
        return

    if result.get("ok"):
        icon_char = status.get("icon", "")
        if not text:
            print("Status cleared")
        elif icon_char:
            print(f"{icon_char}  {text}")
        else:
            print(text)
    else:
        notify_error(f"Slack API error: {result.get('error', 'unknown')}")


if __name__ == "__main__":
    main()
