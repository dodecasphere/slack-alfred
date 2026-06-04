#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
import urllib.request

CONFIG_FILE      = os.path.expanduser("~/.config/slack-alfred/config.json")
USAGE_FILE       = os.path.expanduser("~/.config/slack-alfred/usage.json")
TOKEN_ERROR_FLAG = os.path.expanduser("~/.config/slack-alfred/token_error")
SETUP_URL        = "https://api.slack.com/apps"

_AUTH_ERRORS = {"invalid_auth", "token_revoked", "account_inactive", "not_authed"}


def set_token_error_flag():
    try:
        os.makedirs(os.path.dirname(TOKEN_ERROR_FLAG), exist_ok=True)
        open(TOKEN_ERROR_FLAG, "w").close()
    except Exception:
        pass


def clear_token_error_flag():
    try:
        os.remove(TOKEN_ERROR_FLAG)
    except FileNotFoundError:
        pass


def load_usage():
    try:
        with open(USAGE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def record_usage(title):
    if not title:
        return
    usage = load_usage()
    entry = usage.get(title, {"count": 0, "last_used": 0})
    entry["count"] += 1
    entry["last_used"] = int(time.time())
    usage[title] = entry
    try:
        with open(USAGE_FILE, "w") as f:
            json.dump(usage, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except Exception:
        pass


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


def set_slack_status(token, text, emoji, expiry=0):
    payload = json.dumps({
        "profile": {
            "status_text": text,
            "status_emoji": emoji,
            "status_expiration": expiry,
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


def save_preset(status):
    text  = status.get("text", "").strip()
    icon  = status.get("icon", "💬").strip()
    emoji = status.get("emoji", "").strip()

    if not text:
        notify_error("No status text to save.")
        return

    config = load_config()
    if not config:
        notify_error("Couldn't read config file.")
        return

    statuses = config.get("statuses", [])
    if any(s.get("title") == text for s in statuses):
        print(f"Already in presets: {text}")
        return

    expiry_config = status.get("expiry_config", "")
    entry = {"title": text, "text": text, "emoji": emoji, "icon": icon}
    if expiry_config:
        entry["expiry"] = expiry_config
    statuses.append(entry)
    config["statuses"] = statuses

    try:
        save_config(config)
    except Exception as e:
        notify_error(f"Couldn't save preset: {e}")
        return

    print(f"{icon}  Preset saved: {text}")


def update_preset(status):
    title         = status.get("title", "").strip()
    expiry_config = status.get("expiry_config", "")

    if not title:
        notify_error("No preset title specified.")
        return

    config = load_config()
    if not config:
        notify_error("Couldn't read config file.")
        return

    statuses = config.get("statuses", [])
    updated = False
    for s in statuses:
        if s.get("title") == title:
            if expiry_config:
                s["expiry"] = expiry_config
            else:
                s.pop("expiry", None)
            updated = True
            break

    if not updated:
        notify_error(f"Preset not found: {title}")
        return

    try:
        save_config(config)
    except Exception as e:
        notify_error(f"Couldn't update preset: {e}")
        return

    text      = status.get("text", "")
    emoji     = status.get("emoji", "")
    expiry    = int(status.get("expiry", 0))
    icon_char = status.get("icon", "")

    try:
        result = set_slack_status(config["token"], text, emoji, expiry)
    except Exception as e:
        notify_error(f"Request failed: {e}")
        return

    if result.get("ok"):
        record_usage(title)
        clear_token_error_flag()
        suffix = f" · {expiry_config} expiry saved" if expiry_config else ""
        print(f"{icon_char}  {text}{suffix}" if icon_char else f"{text}{suffix}")
    else:
        error = result.get("error", "unknown")
        if error in _AUTH_ERRORS:
            set_token_error_flag()
            print("❌ Token rejected — type slacks in Alfred and Tab to update")
        else:
            notify_error(f"Slack API error: {error}")


def save_token(status):
    token = status.get("token", "").strip()
    if not token.startswith("xoxp-"):
        notify_error("Token must start with xoxp-")
        return

    config = load_config() or {}
    config["token"] = token
    try:
        save_config(config)
    except Exception as e:
        notify_error(f"Couldn't save token: {e}")
        return

    clear_token_error_flag()
    print("✓  Token saved")


def remove_preset(status):
    title = status.get("title", "").strip()
    if not title:
        notify_error("No preset title specified.")
        return

    config = load_config()
    if not config:
        notify_error("Couldn't read config file.")
        return

    statuses = config.get("statuses", [])
    filtered = [s for s in statuses if s.get("title") != title]
    if len(filtered) == len(statuses):
        notify_error(f"Preset not found: {title}")
        return

    config["statuses"] = filtered
    try:
        save_config(config)
    except Exception as e:
        notify_error(f"Couldn't remove preset: {e}")
        return

    print(f"Preset removed: {title}")


def do_setup():
    subprocess.run(["open", SETUP_URL])
    steps = (
        "1. Create a new Slack app at api.slack.com/apps\\n"
        "2. From scratch → name it, pick your workspace\\n"
        "3. OAuth & Permissions → User Token Scopes → add: users.profile:write  users:write\\n"
        "4. Install to Workspace → copy the xoxp- token\\n"
        "5. Run ./setup.sh in the repo folder"
    )
    script = (
        f'display dialog "Slack Status Setter — Setup\\n\\n{steps}" '
        f'with title "Slack Status Setup" '
        f'buttons {{"OK"}} default button "OK"'
    )
    subprocess.Popen(["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    arg = sys.stdin.read().strip()

    if arg == "setup":
        do_setup()
        return

    config = load_config()
    if not config or not config.get("token"):
        notify_error("No token configured — run 'slacks' in Alfred to set up.")
        return

    try:
        status = json.loads(arg)
    except json.JSONDecodeError:
        notify_error(f"Unexpected input: {arg!r}")
        return

    _ACTIONS = {
        "save_preset":   save_preset,
        "update_preset": update_preset,
        "remove_preset": remove_preset,
        "save_token":    save_token,
    }
    handler = _ACTIONS.get(status.get("action"))
    if handler:
        handler(status)
        return

    text   = status.get("text", "")
    emoji  = status.get("emoji", "")
    expiry = int(status.get("expiry", 0))

    try:
        result = set_slack_status(config["token"], text, emoji, expiry)
    except Exception as e:
        notify_error(f"Request failed: {e}")
        return

    if result.get("ok"):
        record_usage(status.get("title"))
        clear_token_error_flag()
        icon_char = status.get("icon", "")
        if not text:
            print("Status cleared")
        elif icon_char:
            print(f"{icon_char}  {text}")
        else:
            print(text)
    else:
        error = result.get("error", "unknown")
        if error in _AUTH_ERRORS:
            set_token_error_flag()
            print("❌ Token rejected — type slacks in Alfred and Tab to update")
        else:
            notify_error(f"Slack API error: {error}")


if __name__ == "__main__":
    main()
