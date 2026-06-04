#!/usr/bin/env python3
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from filter import load_config, with_icon


def main():
    query  = sys.stdin.read().strip().lower()
    config = load_config()

    if not config or not config.get("token"):
        print(json.dumps({"items": [{
            "title":    "Setup Required — run 'slacks' first",
            "subtitle": "Your Slack token is not configured yet",
            "valid":    False,
        }]}))
        return

    items = [
        with_icon({
            "title":    "Active",
            "subtitle": "Set your Slack presence to active",
            "arg":      "auto",
            "valid":    True,
        }, "🟢"),
        with_icon({
            "title":    "Away",
            "subtitle": "Set your Slack presence to away",
            "arg":      "away",
            "valid":    True,
        }, "⏸️"),
    ]

    if query:
        items = [i for i in items if query in i["title"].lower()]

    print(json.dumps({"items": items}))


if __name__ == "__main__":
    main()
