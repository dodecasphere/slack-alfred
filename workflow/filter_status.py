#!/usr/bin/env python3
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import (
    load_config, load_usage, _usage_score,
    TOKEN_ERROR_FLAG, _SUBMENU_PREFIX, _REMOVE_SUFFIX, _TOKEN_SUBMENU,
    DEFAULT_STATUSES, with_icon, compute_expiry_from_config, parse_custom_status,
    split_submenu_query, build_expiry_submenu, build_remove_confirm_submenu,
    build_token_submenu, build_setup_item, build_token_error_item,
)


def main():
    raw   = sys.stdin.read().strip()
    query = raw.lower()

    # Token submenu must be reachable regardless of config state (used during initial setup too)
    if raw.startswith(_SUBMENU_PREFIX):
        inner = raw[len(_SUBMENU_PREFIX):]
        if inner == _TOKEN_SUBMENU or inner.startswith(_TOKEN_SUBMENU + " "):
            token_input = inner[len(_TOKEN_SUBMENU):].strip()
            print(json.dumps({"items": build_token_submenu(token_input)}))
            return

    config = load_config()

    if not config or not config.get("token"):
        print(json.dumps({"items": [build_setup_item()]}))
        return

    statuses = [s for s in config.get("statuses", DEFAULT_STATUSES)
                if s.get("title") != "Clear status"]

    usage = load_usage()
    statuses = sorted(statuses,
                      key=lambda s: (-_usage_score(usage.get(s["title"], {})),
                                     s["title"].lower()))

    # Remaining submenu routing — preset expiry and remove confirm
    if raw.startswith(_SUBMENU_PREFIX):
        inner = raw[len(_SUBMENU_PREFIX):]
        if inner.endswith(_REMOVE_SUFFIX):
            preset_title = inner[:-len(_REMOVE_SUFFIX)]
            items = build_remove_confirm_submenu(preset_title, statuses)
        else:
            title, custom = split_submenu_query(inner, statuses)
            items = build_expiry_submenu(title, custom, statuses)
        print(json.dumps({"items": items}))
        return

    items = []

    if os.path.exists(TOKEN_ERROR_FLAG):
        print(json.dumps({"items": [build_token_error_item()]}))
        return

    # Clear status — hardcoded, no submenu
    if not query or query in "clear status":
        items.append(with_icon({
            "title":    "Clear status",
            "subtitle": "Clear your current status",
            "arg":      json.dumps({"text": "", "emoji": "", "icon": "🧹", "expiry": 0, "expiry_config": ""}),
            "valid":    True,
        }, "🧹"))

    for s in statuses:
        title_match = query in s["title"].lower()
        text_match  = query and query in s["text"].lower()
        if query and not title_match and not text_match:
            continue

        expiry_ts, expiry_display = compute_expiry_from_config(s.get("expiry", ""))

        subtitle = f"{s['emoji']}  {s['text']}"
        if expiry_display:
            subtitle += f" · {expiry_display}"

        items.append(with_icon({
            "title":        s["title"],
            "subtitle":     subtitle,
            "autocomplete": f"{_SUBMENU_PREFIX}{s['title']}",
            "arg": json.dumps({
                "text":          s["text"],
                "emoji":         s["emoji"],
                "icon":          s.get("icon", ""),
                "expiry":        expiry_ts,
                "expiry_config": s.get("expiry", ""),
                "title":         s["title"],
            }),
            "valid": True,
        }, s.get("icon", "")))

    # Custom status
    if query and not any(query == s["title"].lower() for s in statuses):
        icon_char, slack_emoji, status_text, expiry_ts, expiry_display, expiry_config = \
            parse_custom_status(raw)

        if icon_char == "💬" and slack_emoji == ":speech_balloon:":
            subtitle = "💬  Lead with an emoji for a custom icon"
        elif icon_char == "💬":
            subtitle = f"💬  {slack_emoji} Slack emoji"
        elif slack_emoji == icon_char:
            subtitle = f"{icon_char}  Icon & Slack emoji"
        else:
            subtitle = f"{icon_char}  Icon · {slack_emoji} Slack emoji"

        if expiry_display:
            subtitle += f" · {expiry_display}"
        subtitle += " · ⌘↩ to save as preset"

        set_arg  = json.dumps({"text": status_text, "emoji": slack_emoji, "icon": icon_char,
                               "expiry": expiry_ts, "expiry_config": expiry_config})
        save_arg = json.dumps({"text": status_text, "emoji": slack_emoji, "icon": icon_char,
                               "expiry": expiry_ts, "expiry_config": expiry_config,
                               "action": "save_preset"})
        items.append(with_icon({
            "title":    f'Custom: "{status_text}"',
            "subtitle": subtitle,
            "arg":      set_arg,
            "valid":    True,
            "mods": {
                "cmd": {
                    "subtitle": f"{icon_char}  Save as preset",
                    "arg":      save_arg,
                    "valid":    True,
                }
            },
        }, icon_char))

    if not items:
        items.append({
            "title":    "No matching statuses",
            "subtitle": "Keep typing to create a custom status",
            "valid":    False,
        })

    print(json.dumps({"items": items}))


if __name__ == "__main__":
    main()
