#!/usr/bin/env python3
import json
import os
import sys

CONFIG_FILE = os.path.expanduser("~/.config/slack-alfred/config.json")

DEFAULT_STATUSES = [
    {"title": "Clear status",        "emoji": "",                        "text": "",                    "icon": "🧹"},
    {"title": "In a meeting",        "emoji": ":calendar:",              "text": "In a meeting",        "icon": "📅"},
    {"title": "Focusing",            "emoji": ":headphones:",            "text": "Focusing",            "icon": "🎧"},
    {"title": "Lunch break",         "emoji": ":fork_and_knife:",        "text": "Lunch break",         "icon": "🍴"},
    {"title": "Out sick",            "emoji": ":face_with_thermometer:", "text": "Out sick",            "icon": "🤒"},
    {"title": "Vacationing",         "emoji": ":palm_tree:",             "text": "Vacationing",         "icon": "🌴"},
    {"title": "Working from home",   "emoji": ":house:",                 "text": "Working from home",   "icon": "🏠"},
    {"title": "Do not disturb",      "emoji": ":no_entry_sign:",         "text": "Do not disturb",      "icon": "🔕"},
    {"title": "Commuting",           "emoji": ":bus:",                   "text": "Commuting",           "icon": "🚌"},
    {"title": "Coffee break",        "emoji": ":coffee:",                "text": "Coffee break",        "icon": "☕"},
    {"title": "On a call",           "emoji": ":telephone_receiver:",    "text": "On a call",           "icon": "📞"},
    {"title": "Be right back",       "emoji": ":brb:",                   "text": "Be right back",       "icon": "🔙"},
]


def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def emoji_icon(char):
    return {"type": "text", "text": char}


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
                "icon": emoji_icon("⚙️"),
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
            item["icon"] = emoji_icon(s["icon"])
        items.append(item)

    if query and not any(query == s["title"].lower() for s in statuses):
        items.append({
            "title": f'Custom: "{raw}"',
            "subtitle": ":speech_balloon:  Set as custom status",
            "arg": json.dumps({"text": raw, "emoji": ":speech_balloon:"}),
            "valid": True,
            "icon": emoji_icon("💬"),
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
