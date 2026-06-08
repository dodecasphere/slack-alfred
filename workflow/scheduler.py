#!/usr/bin/env python3
"""
Schedule dispatcher — run by a launchd LaunchAgent every 60s.

Loads `schedules` from config.json, fires any that are due (within a grace
window so a poll that lands a few seconds late still triggers), dedupes via a
per-occurrence key in schedule_state.json, deletes fired/missed one-offs, and
posts a macOS notification for each fire.
"""
import json
import os
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (load_config, save_config, load_schedule_state,
                    save_schedule_state, set_slack_status, evaluate_schedule,
                    compute_expiry_from_config, write_current_status_cache)

_GRACE_SECONDS    = 300       # fire if a due time is at most this late
_FIRED_KEY_TTL    = 2 * 86400  # prune fired-occurrence keys older than this


def notify(title, message):
    script = f'display notification {json.dumps(message)} with title {json.dumps(title)}'
    subprocess.Popen(["osascript", "-e", script],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def fire(token, sched):
    text  = sched.get("text", "")
    emoji = sched.get("emoji", "")
    icon  = sched.get("icon", "")
    expiry_ts, _ = compute_expiry_from_config(sched.get("expiry", ""))
    try:
        result = set_slack_status(token, text, emoji, expiry_ts)
    except Exception as e:
        notify("⚠️ Scheduled status failed", f"{text}: {e}")
        return False
    if result.get("ok"):
        write_current_status_cache(text, emoji, expiry_ts)
        notify("🕒 Slack status set", f"{icon}  {text}".strip())
        return True
    notify("⚠️ Scheduled status failed",
           f"{text}: {result.get('error', 'unknown')}")
    return False


def main():
    config = load_config()
    if not config or not config.get("token"):
        return
    schedules = config.get("schedules", [])
    if not schedules:
        return

    token = config["token"]
    state = load_schedule_state()
    fired = state.get("fired", {})
    now   = datetime.now()
    now_ts = now.timestamp()

    keep          = []
    config_dirty  = False

    for sched in schedules:
        action, key = evaluate_schedule(sched, now, set(fired), _GRACE_SECONDS)

        if action == "fire":
            fire(token, sched)
            if sched.get("kind") == "one_off":
                config_dirty = True          # drop it (don't keep)
                continue
            fired[key] = now_ts              # recurring: remember occurrence
            keep.append(sched)
        elif action == "expire":
            notify("🕒 Missed scheduled status",
                   f"{sched.get('text', '')} (was due earlier)")
            config_dirty = True              # drop the stale one-off
        else:
            keep.append(sched)

    # Prune old fired-occurrence keys.
    fired = {k: v for k, v in fired.items() if now_ts - v < _FIRED_KEY_TTL}
    save_schedule_state({"fired": fired})

    if config_dirty:
        config["schedules"] = keep
        save_config(config)


if __name__ == "__main__":
    main()
