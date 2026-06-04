#!/usr/bin/env python3
"""
Downloads iamcal/emoji-data and writes workflow/emoji.json —
a compact {shortname: unicode_char} mapping for :emoji: autocomplete.
Run by build.sh; safe to run manually to refresh.
"""
import json
import os
import urllib.request

SOURCE = "https://raw.githubusercontent.com/iamcal/emoji-data/master/emoji.json"
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emoji.json")


def unified_to_char(unified):
    return "".join(chr(int(cp, 16)) for cp in unified.split("-"))


def main():
    print("Fetching emoji list…", end=" ", flush=True)
    try:
        with urllib.request.urlopen(SOURCE, timeout=15) as r:
            data = json.load(r)
    except Exception as e:
        if os.path.exists(OUTPUT):
            print(f"skipped (offline) — using existing {os.path.basename(OUTPUT)}")
        else:
            print(f"failed ({e})")
        return

    mapping = {}
    for entry in data:
        char = unified_to_char(entry["unified"])
        for name in entry.get("short_names", []):
            mapping[name] = char

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, separators=(",", ":"))

    print(f"✓  {len(mapping)} codes → {os.path.basename(OUTPUT)}")


if __name__ == "__main__":
    main()
