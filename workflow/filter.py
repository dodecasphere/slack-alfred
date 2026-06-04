#!/usr/bin/env python3
import json
import os
import subprocess
import sys

CONFIG_FILE = os.path.expanduser("~/.config/slack-alfred/config.json")
ICON_CACHE  = os.path.expanduser("~/.config/slack-alfred/icons")

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

_JXA = """\
ObjC.import('AppKit');
var emoji=EMOJI,size=160,out=OUTPATH;
var rep=$.NSBitmapImageRep.alloc\
.initWithBitmapDataPlanesPixelsWidePixelsHighBitsPerSampleSamplesPerPixelHasAlphaIsPlanarColorSpaceNameBitmapFormatBytesPerRowBitsPerPixel(
    null,size,size,8,4,true,false,"NSCalibratedRGBColorSpace",0,0,0);
$.NSGraphicsContext.setCurrentContext($.NSGraphicsContext.graphicsContextWithBitmapImageRep(rep));
var font=$.NSFont.systemFontOfSize(size*0.80),attrs=ObjC.wrap({"NSFont":font});
var str=$.NSString.stringWithString(emoji),sz=str.sizeWithAttributes(attrs);
str.drawAtPointWithAttributes($.NSMakePoint((size-sz.width)/2,(size-sz.height)/2),attrs);
rep.representationUsingTypeProperties(4,ObjC.wrap({})).writeToFileAtomically(out,true);
"""


def icon_path(emoji_char):
    """Return the cached PNG path if it exists, otherwise kick off background generation."""
    if not emoji_char:
        return None
    name = "_".join(f"{ord(c):04X}" for c in emoji_char if ord(c) > 31)
    path = os.path.join(ICON_CACHE, f"{name}.png")
    if os.path.exists(path):
        return path
    # Not cached yet — generate in the background so this invocation stays fast.
    # The icon will be ready by the next time Alfred re-runs the filter.
    os.makedirs(ICON_CACHE, exist_ok=True)
    jxa = _JXA.replace("EMOJI", json.dumps(emoji_char)).replace("OUTPATH", json.dumps(path))
    subprocess.Popen(["osascript", "-l", "JavaScript", "-e", jxa],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return None


def with_icon(item, emoji_char):
    p = icon_path(emoji_char)
    if p:
        item["icon"] = {"path": p}
    return item


def split_emoji_prefix(text):
    """
    '🏋️ at the gym' → ('🏋️', 'at the gym')
    'be right back'  → (None, 'be right back')
    First whitespace-delimited token is treated as an icon emoji if it
    starts above U+00FF (i.e. not plain ASCII/Latin).
    """
    parts = text.split(" ", 1)
    if len(parts) == 2 and parts[1] and ord(parts[0][0]) > 0x00FF:
        return parts[0], parts[1].strip()
    return None, text


def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def main():
    raw = sys.stdin.read().strip()
    query = raw.lower()
    config = load_config()

    if not config or not config.get("token"):
        print(json.dumps({"items": [with_icon({
            "title": "Setup Required — Press Enter",
            "subtitle": "Opens Slack API page to generate your token",
            "arg": "setup",
            "valid": True,
        }, "⚙️")]}))
        return

    statuses = config.get("statuses", DEFAULT_STATUSES)
    items = []

    for s in statuses:
        title_match = query in s["title"].lower()
        text_match = query and query in s["text"].lower()
        if query and not title_match and not text_match:
            continue

        subtitle = f"{s['emoji']}  {s['text']}" if s["emoji"] else "Clear your current status"
        items.append(with_icon({
            "title": s["title"],
            "subtitle": subtitle,
            "arg": json.dumps({"text": s["text"], "emoji": s["emoji"]}),
            "valid": True,
        }, s.get("icon", "")))

    # Custom status: parse a leading emoji if present, hint if not
    if query and not any(query == s["title"].lower() for s in statuses):
        icon_char, status_text = split_emoji_prefix(raw)
        if icon_char:
            subtitle = f"{icon_char}  Set as custom status"
        else:
            icon_char = "💬"
            status_text = raw
            subtitle = "💬  Set as custom — or start with an emoji for a custom icon"
        items.append(with_icon({
            "title": f'Custom: "{status_text}"',
            "subtitle": subtitle,
            "arg": json.dumps({"text": status_text, "emoji": ":speech_balloon:"}),
            "valid": True,
        }, icon_char))

    if not items:
        items.append({
            "title": "No matching statuses",
            "subtitle": "Keep typing to create a custom status",
            "valid": False,
        })

    # Always offer to add a new preset at the bottom
    items.append(with_icon({
        "title": "Add new preset…",
        "subtitle": "Save a new entry to your config file",
        "arg": "add_preset",
        "valid": True,
    }, "➕"))

    print(json.dumps({"items": items}))


if __name__ == "__main__":
    main()
