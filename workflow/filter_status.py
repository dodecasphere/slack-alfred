#!/usr/bin/env python3
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import (
    load_config, load_usage, _usage_score,
    TOKEN_ERROR_FLAG, CUSTOM_EMOJI_CACHE, CUSTOM_EMOJI_IMAGES_DONE,
    _SUBMENU_PREFIX, _REMOVE_SUFFIX, _TOKEN_SUBMENU,
    DEFAULT_STATUSES, with_icon, cached_icon_path, compute_expiry_from_config,
    parse_custom_status, extract_bracket_title, split_submenu_query,
    build_expiry_submenu, build_edit_submenu, _EDIT_INFIX,
    build_remove_confirm_submenu, build_token_submenu, build_setup_item,
    build_token_error_item, search_emoji, _refresh_custom_emoji_async,
    build_current_status_item,
)

# Matches a trailing uncompleted :emoji_fragment — triggers emoji suggestion mode
_EMOJI_TRIGGER = re.compile(r':([a-z0-9_+\-]+)$', re.IGNORECASE)


def _build_emoji_suggestions(raw, fragment):
    """Return Alfred items for :fragment emoji suggestions."""
    prefix  = raw[: raw.rfind(":" + fragment)]
    matches = search_emoji(fragment)
    items   = []
    for code, char in matches:
        full_query = f"{prefix}:{code}: "
        item = {
            "title":        f":{code}:",
            "autocomplete": full_query,
            "valid":        False,
        }
        # Use cached_icon_path to avoid spawning JXA for each uncached emoji
        p = cached_icon_path(char if char else f":{code}:")
        if p:
            item["icon"] = {"path": p}
        items.append(item)
    return items


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

    token = config["token"]

    # Ensure custom emoji and their images are fetched. Re-triggers if either the
    # JSON cache or the images-done sentinel is missing (covers existing users
    # whose cache was written before image downloading was added).
    if not os.path.exists(CUSTOM_EMOJI_CACHE) or not os.path.exists(CUSTOM_EMOJI_IMAGES_DONE):
        _refresh_custom_emoji_async()

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
            if custom == _EDIT_INFIX or custom.startswith(_EDIT_INFIX + " "):
                edit_query = custom[len(_EDIT_INFIX):].strip()
                items = build_edit_submenu(title, edit_query, statuses)
            else:
                items = build_expiry_submenu(title, custom, statuses)
        print(json.dumps({"items": items}))
        return

    if os.path.exists(TOKEN_ERROR_FLAG):
        print(json.dumps({"items": [build_token_error_item()]}))
        return

    # Emoji suggestion mode — trailing :fragment triggers inline emoji search
    emoji_m = _EMOJI_TRIGGER.search(raw)
    if emoji_m:
        suggestions = _build_emoji_suggestions(raw, emoji_m.group(1))
        if suggestions:
            print(json.dumps({"items": suggestions}))
            return

    items = [build_current_status_item(token)] if not query else []

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
        bracket_title, raw_for_parse = extract_bracket_title(raw)
        icon_char, slack_emoji, status_text, expiry_ts, expiry_display, expiry_config = \
            parse_custom_status(raw_for_parse)

        if icon_char == "💬" and slack_emoji == ":speech_balloon:":
            subtitle = "💬  Lead with an emoji for a custom icon"
        elif slack_emoji == icon_char:
            subtitle = f"{icon_char}  Icon & Slack emoji"
        else:
            subtitle = f"{icon_char}  Icon · {slack_emoji} Slack emoji"

        if expiry_display:
            subtitle += f" · {expiry_display}"
        if bracket_title:
            subtitle += f" · ⌘↩ to save as \"{bracket_title}\""
        else:
            subtitle += " · ⌘↩ to save as preset"

        set_arg  = json.dumps({"text": status_text, "emoji": slack_emoji, "icon": icon_char,
                               "expiry": expiry_ts, "expiry_config": expiry_config})
        save_arg_d = {"text": status_text, "emoji": slack_emoji, "icon": icon_char,
                      "expiry": expiry_ts, "expiry_config": expiry_config,
                      "action": "save_preset"}
        if bracket_title:
            save_arg_d["title"] = bracket_title
        save_arg = json.dumps(save_arg_d)

        save_subtitle = f"Save as \"{bracket_title}\"" if bracket_title else f"{icon_char}  Save as preset"
        items.append(with_icon({
            "title":    f'Custom: "{status_text}"',
            "subtitle": subtitle,
            "arg":      set_arg,
            "valid":    True,
            "mods": {
                "cmd": {
                    "subtitle": save_subtitle,
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

    output = {"items": items}
    # Re-run every second while the current status item is loading or active so
    # the fetch resolves, expiry countdown ticks, and clears reflect immediately.
    first = items[0].get("title", "") if items else ""
    if first == "Fetching status…" or first.startswith("Current status: "):
        output["rerun"] = 1
    print(json.dumps(output))


if __name__ == "__main__":
    main()
