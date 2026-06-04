#!/usr/bin/env python3
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import (load_config, with_icon, TOKEN_ERROR_FLAG,
                    _SUBMENU_PREFIX, _TOKEN_SUBMENU, build_token_submenu)


def main():
    raw   = sys.stdin.read().strip()
    query = raw.lower()
    config = load_config()

    if not config or not config.get("token"):
        print(json.dumps({"items": [{
            "title":    "Setup Required — run 'slacks' first",
            "subtitle": "Your Slack token is not configured yet",
            "valid":    False,
        }]}))
        return

    if raw.startswith(_SUBMENU_PREFIX):
        inner = raw[len(_SUBMENU_PREFIX):]
        if inner == _TOKEN_SUBMENU or inner.startswith(_TOKEN_SUBMENU + " "):
            token_input = inner[len(_TOKEN_SUBMENU):].strip()
            print(json.dumps({"items": build_token_submenu(token_input)}))
            return

    if os.path.exists(TOKEN_ERROR_FLAG):
        print(json.dumps({"items": [{
            "title":        "⚠️ Token invalid — Tab to update",
            "subtitle":     "Slack rejected your token. Tab or → to paste a new one.",
            "autocomplete": f"{_SUBMENU_PREFIX}{_TOKEN_SUBMENU} ",
            "valid":        False,
        }]}))
        return

    items = [
        with_icon({
            "title":    "Active",
            "subtitle": "Set your Slack presence to active",
            "arg":      "auto",
            "valid":    True,
        }, "🧑‍💻"),
        with_icon({
            "title":    "Away",
            "subtitle": "Set your Slack presence to away",
            "arg":      "away",
            "valid":    True,
        }, "🏃"),
    ]

    if query:
        items = [i for i in items if query in i["title"].lower()]

    print(json.dumps({"items": items}))


if __name__ == "__main__":
    main()
