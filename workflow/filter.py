#!/usr/bin/env python3
import json
import os
import sys

CONFIG_FILE = os.path.expanduser("~/.config/slack-alfred/config.json")

DEFAULT_STATUSES = [
    {"title": "Clear status",        "emoji": "",                        "text": "",                    "icon": "clear.png"},
    {"title": "In a meeting",        "emoji": ":calendar:",              "text": "In a meeting",        "icon": "meeting.png"},
    {"title": "Focusing",            "emoji": ":headphones:",            "text": "Focusing",            "icon": "focusing.png"},
    {"title": "Lunch break",         "emoji": ":fork_and_knife:",        "text": "Lunch break",         "icon": "lunch.png"},
    {"title": "Out sick",            "emoji": ":face_with_thermometer:", "text": "Out sick",            "icon": "sick.png"},
    {"title": "Vacationing",         "emoji": ":palm_tree:",             "text": "Vacationing",         "icon": "vacation.png"},
    {"title": "Working from home",   "emoji": ":house:",                 "text": "Working from home",   "icon": "wfh.png"},
    {"title": "Do not disturb",      "emoji": ":no_entry_sign:",         "text": "Do not disturb",      "icon": "dnd.png"},
    {"title": "Commuting",           "emoji": ":bus:",                   "text": "Commuting",           "icon": "commute.png"},
    {"title": "Coffee break",        "emoji": ":coffee:",                "text": "Coffee break",        "icon": "coffee.png"},
    {"title": "On a call",           "emoji": ":telephone_receiver:",    "text": "On a call",           "icon": "call.png"},
    {"title": "Be right back",       "emoji": ":brb:",                   "text": "Be right back",       "icon": "brb.png"},
]


def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def icon(filename):
    return {"path": f"icons/{filename}"}


def main():
    raw = sys.stdin.read().strip()
    query = raw.lower()
    config = load_config()

    if not config or not config.get("token"):
        print(json.dumps({
            "items": [{
                "title": "Setup Required — Press Enter",
                "subtitle": "Opens Slack API page to generate your token",
                "arg": "setup",
                "valid": True,
                "icon": icon("setup.png"),
            }]
        }))
        return

    statuses = config.get("statuses", DEFAULT_STATUSES)
    items = []

    for s in statuses:
        title_match = query in s["title"].lower()
        text_match = query and query in s["text"].lower()
        if query and not title_match and not text_match:
            continue

        subtitle = f"{s['emoji']}  {s['text']}" if s["emoji"] else "Clear your current status"
        item = {
            "title": s["title"],
            "subtitle": subtitle,
            "arg": json.dumps({"text": s["text"], "emoji": s["emoji"]}),
            "valid": True,
        }
        if s.get("icon"):
            item["icon"] = icon(s["icon"])
        items.append(item)

    # Offer to set whatever the user typed as a custom status
    if query and not any(query == s["title"].lower() for s in statuses):
        items.append({
            "title": f'Custom: "{raw}"',
            "subtitle": ":speech_balloon:  Set as custom status",
            "arg": json.dumps({"text": raw, "emoji": ":speech_balloon:"}),
            "valid": True,
            "icon": icon("custom.png"),
        })

    if not items:
        items.append({
            "title": "No matching statuses",
            "subtitle": "Keep typing to create a custom status",
            "valid": False,
        })

    print(json.dumps({"items": items}))


if __name__ == "__main__":
    main()
