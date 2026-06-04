#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta

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

_SLACK_CODE      = re.compile(r'(:[a-z0-9_+\-]+:)', re.IGNORECASE)
_SUBMENU_PREFIX  = "» "
_REMOVE_SUFFIX   = " » remove"


# ── Icon cache ────────────────────────────────────────────────────────────────

def icon_path(emoji_char):
    if not emoji_char:
        return None
    name = "_".join(f"{ord(c):04X}" for c in emoji_char if ord(c) > 31)
    path = os.path.join(ICON_CACHE, f"{name}.png")
    if os.path.exists(path):
        return path
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


# ── Expiry parsing ────────────────────────────────────────────────────────────

def parse_duration(text):
    """
    Parse a human duration string into seconds. Returns None if unrecognized.

    Accepts: 2h, 2hr, 2hrs, 2hour, 2hours, 2m, 2min, 2mins, 2minutes,
             1h30m, 1h 30m, 1.5h, 90 (bare integer = minutes)
    """
    t = text.strip().lower()

    m = re.fullmatch(
        r'(\d+(?:\.\d+)?)\s*h(?:r|rs|our|ours)?'
        r'(?:\s*(\d+)\s*m(?:in|ins|inute|inutes)?)?', t)
    if m:
        return int(float(m.group(1)) * 3600 + int(m.group(2) or 0) * 60)

    m = re.fullmatch(r'(\d+(?:\.\d+)?)\s*m(?:in|ins|inute|inutes)?', t)
    if m:
        return int(float(m.group(1)) * 60)

    if re.fullmatch(r'\d+', t):
        return int(t) * 60

    return None


def parse_until_time(text):
    """
    Parse a time expression and return (unix_timestamp, '2:00 PM') for the
    next occurrence of that time. Returns (None, None) if unrecognized.

    Accepts: 2pm, 2p, 2:30pm, 14:00, noon, midnight, 2 o'clock, 2 o'clock pm
    """
    t = text.strip().lower()
    now = datetime.now()

    def resolve(hour, minute=0):
        dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if dt <= now:
            dt += timedelta(days=1)
        return int(dt.timestamp()), dt.strftime("%-I:%M %p")

    if t == "noon":
        return resolve(12)
    if t == "midnight":
        return resolve(0)

    hour = minute = ampm = None

    m = re.fullmatch(r'(\d{1,2}):(\d{2})\s*(am?|pm?)?', t)
    if m:
        hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3)

    if hour is None:
        m = re.fullmatch(r"(\d{1,2})(?:\s+o'?clock)?\s*(am?|pm?)?", t)
        if m:
            hour, minute, ampm = int(m.group(1)), 0, m.group(2)

    if hour is None:
        return None, None

    if ampm in ('pm', 'p') and hour != 12:
        hour += 12
    elif ampm in ('am', 'a') and hour == 12:
        hour = 0
    elif ampm is None and 1 <= hour <= 11:
        # No am/pm — pick whichever of AM or PM comes next
        pm_dt = now.replace(hour=hour + 12, minute=minute, second=0, microsecond=0)
        am_dt = now.replace(hour=hour,      minute=minute, second=0, microsecond=0)
        if pm_dt <= now:
            pm_dt += timedelta(days=1)
        if am_dt <= now:
            am_dt += timedelta(days=1)
        if pm_dt < am_dt:
            hour += 12

    if not 0 <= hour <= 23:
        return None, None

    return resolve(hour, minute)


def _fmt_duration(secs):
    if secs < 3600:
        return f"{secs // 60}m"
    if secs % 3600 == 0:
        return f"{secs // 3600}h"
    return f"{secs // 3600}h {(secs % 3600) // 60}m"


def extract_expiry(text):
    """
    Strip 'for <duration>' or 'until <time>' from the end of text.
    Returns (expiry_ts, expiry_display, expiry_config_str, clean_text).
    expiry_ts=0 means no expiry.
    """
    m = re.search(r'\bfor\s+(.+)$', text, re.IGNORECASE)
    if m:
        secs = parse_duration(m.group(1).strip())
        if secs is not None:
            label = _fmt_duration(secs)
            return (int(time.time()) + secs,
                    f"expires in {label}",
                    label,
                    text[:m.start()].strip())

    m = re.search(r'\buntil\s+(.+)$', text, re.IGNORECASE)
    if m:
        ts, time_label = parse_until_time(m.group(1).strip())
        if ts is not None:
            return (ts,
                    f"expires at {time_label}",
                    m.group(1).strip(),
                    text[:m.start()].strip())

    return 0, "", "", text


def compute_expiry_from_config(expiry_str):
    """
    Convert a stored expiry string ('2h', '5pm') to (unix_ts, display_label).
    Called when loading presets so expiry is always relative to now.
    """
    if not expiry_str:
        return 0, ""
    secs = parse_duration(expiry_str)
    if secs is not None:
        return int(time.time()) + secs, f"expires in {_fmt_duration(secs)}"
    ts, time_label = parse_until_time(expiry_str)
    if ts:
        return ts, f"expires at {time_label}"
    return 0, ""


# ── Status parsing ────────────────────────────────────────────────────────────

def split_emoji_prefix(text):
    """
    '🏋️ at the gym' → ('🏋️', 'at the gym')
    'be right back'  → (None, 'be right back')
    """
    parts = text.split(" ", 1)
    if len(parts) == 2 and parts[1] and ord(parts[0][0]) > 0x00FF:
        return parts[0], parts[1].strip()
    return None, text


def parse_custom_status(raw):
    """
    Parse free-form query into (menu_icon, slack_emoji, status_text,
                                expiry_ts, expiry_display, expiry_config).

    '🧠 :brain: deep focus for 2h' → ('🧠', ':brain:', 'deep focus', ts, 'expires in 2h', '2h')
    '🏋️ at the gym until 5pm'     → ('🏋️', '🏋️',    'at the gym', ts, 'expires at 5:00 PM', '5pm')
    '🏋️ at the gym'               → ('🏋️', '🏋️',    'at the gym', 0, '', '')
    'be right back'                → ('💬', ':speech_balloon:', 'be right back', 0, '', '')
    """
    icon_char, rest = split_emoji_prefix(raw)

    if not icon_char:
        ts, display, cfg, clean = extract_expiry(raw.strip())
        return "💬", ":speech_balloon:", clean, ts, display, cfg

    m = _SLACK_CODE.search(rest)
    if m:
        slack_emoji = m.group(1)
        remaining   = (rest[:m.start()] + rest[m.end():]).strip()
        ts, display, cfg, clean = extract_expiry(remaining)
        return icon_char, slack_emoji, clean, ts, display, cfg

    ts, display, cfg, clean = extract_expiry(rest)
    return icon_char, icon_char, clean, ts, display, cfg


# ── Submenus ─────────────────────────────────────────────────────────────────

def split_submenu_query(inner, statuses):
    """Split '» Focusing 2h' inner into ('Focusing', '2h'). Longest title wins."""
    for s in sorted(statuses, key=lambda s: len(s["title"]), reverse=True):
        title = s["title"]
        if inner == title:
            return title, ""
        if inner.startswith(title + " "):
            return title, inner[len(title) + 1:].strip()
    return inner, ""


def build_expiry_submenu(preset_title, custom, statuses):
    preset = next((s for s in statuses if s["title"] == preset_title), None)
    if not preset:
        return [{"title": f"Preset not found: {preset_title!r}", "valid": False}]

    icon_char = preset.get("icon", "")
    text      = preset["text"]
    emoji     = preset["emoji"]
    sub       = f"{icon_char}  {text}" if icon_char else text

    expiry_ts, _ = compute_expiry_from_config(preset.get("expiry", ""))

    # ── Set Status (first item) ──────────────────────────────────────────────
    set_item = with_icon({
        "title":    "Set Status",
        "subtitle": sub,
        "arg":      json.dumps({
            "text":          text,
            "emoji":         emoji,
            "icon":          icon_char,
            "expiry":        expiry_ts,
            "expiry_config": preset.get("expiry", ""),
        }),
        "valid": True,
    }, icon_char)

    # ── Fixed duration items ─────────────────────────────────────────────────
    def expiry_item(label, secs):
        cfg      = _fmt_duration(secs)
        ts       = int(time.time()) + secs
        arg_set  = json.dumps({"text": text, "emoji": emoji, "icon": icon_char,
                               "expiry": ts, "expiry_config": cfg})
        arg_save = json.dumps({"action": "update_preset", "title": preset_title,
                               "text": text, "emoji": emoji, "icon": icon_char,
                               "expiry": ts, "expiry_config": cfg})
        return with_icon({
            "title":    label,
            "subtitle": sub,
            "arg":      arg_set,
            "valid":    True,
            "mods": {"cmd": {
                "subtitle": "Save preset with this expiry",
                "arg":      arg_save,
                "valid":    True,
            }},
        }, "⏲️")

    duration_items = [
        expiry_item("Expire in 30 minutes", 1800),
        expiry_item("Expire in 1 hour",     3600),
        expiry_item("Expire in 2 hours",    7200),
    ]

    # ── Custom expiry (live-parsed as user types) ────────────────────────────
    if custom:
        secs = parse_duration(custom)
        if secs is not None:
            cfg   = _fmt_duration(secs)
            ts    = int(time.time()) + secs
            label = f"Expire in {cfg}"
            disp  = f"expires in {cfg}"
        else:
            ts, time_label = parse_until_time(custom)
            if ts is not None:
                cfg   = custom
                label = f"Expire at {time_label}"
                disp  = f"expires at {time_label}"
            else:
                ts = None

        if ts is not None:
            arg_set  = json.dumps({"text": text, "emoji": emoji, "icon": icon_char,
                                   "expiry": ts, "expiry_config": cfg})
            arg_save = json.dumps({"action": "update_preset", "title": preset_title,
                                   "text": text, "emoji": emoji, "icon": icon_char,
                                   "expiry": ts, "expiry_config": cfg})
            custom_item = with_icon({
                "title":    label,
                "subtitle": f"{sub} · {disp}",
                "arg":      arg_set,
                "valid":    True,
                "mods": {"cmd": {
                    "subtitle": "Save preset with this expiry",
                    "arg":      arg_save,
                    "valid":    True,
                }},
            }, "⏲️")
        else:
            custom_item = with_icon({
                "title":    f"'{custom}' — not recognized",
                "subtitle": "Try: 2h, 30m, 3pm, 5:30pm, 17:00",
                "valid":    False,
            }, "⏲️")
    else:
        custom_item = with_icon({
            "title":    "Custom expiry…",
            "subtitle": "Type a duration (2h, 30m) or time (3pm, 5:30pm)",
            "valid":    False,
        }, "⏲️")

    # ── Remove preset (last item) ────────────────────────────────────────────
    remove_item = with_icon({
        "title":        "Remove preset",
        "subtitle":     f"Delete '{preset_title}' from saved presets",
        "autocomplete": f"{_SUBMENU_PREFIX}{preset_title}{_REMOVE_SUFFIX}",
        "valid":        False,
    }, "❌")

    return [set_item] + duration_items + [custom_item, remove_item]


def build_remove_confirm_submenu(preset_title, statuses):
    preset = next((s for s in statuses if s["title"] == preset_title), None)
    if not preset:
        return [{"title": f"Preset not found: {preset_title!r}", "valid": False}]

    icon_char = preset.get("icon", "")
    return [
        with_icon({
            "title":    f"Confirm: Remove '{preset_title}'",
            "subtitle": "This cannot be undone",
            "arg":      json.dumps({"action": "remove_preset", "title": preset_title}),
            "valid":    True,
        }, icon_char),
        {
            "title":    "Cancel",
            "subtitle": "Press Esc to go back",
            "valid":    False,
        },
    ]


# ── Config ────────────────────────────────────────────────────────────────────

def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

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

    # Submenu routing — triggered when right-arrow is pressed on a preset item
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

    for s in statuses:
        title_match = query in s["title"].lower()
        text_match  = query and query in s["text"].lower()
        if query and not title_match and not text_match:
            continue

        expiry_ts, expiry_display = compute_expiry_from_config(s.get("expiry", ""))

        if s["emoji"]:
            subtitle = f"{s['emoji']}  {s['text']}"
        else:
            subtitle = "Clear your current status"
        if expiry_display:
            subtitle += f" · {expiry_display}"

        items.append(with_icon({
            "title":        s["title"],
            "subtitle":     subtitle,
            "autocomplete": f"{_SUBMENU_PREFIX}{s['title']}",
            "arg": json.dumps({
                "text":         s["text"],
                "emoji":        s["emoji"],
                "icon":         s.get("icon", ""),
                "expiry":       expiry_ts,
                "expiry_config": s.get("expiry", ""),
            }),
            "valid": True,
        }, s.get("icon", "")))

    # Custom status
    if query and not any(query == s["title"].lower() for s in statuses):
        icon_char, slack_emoji, status_text, expiry_ts, expiry_display, expiry_config = \
            parse_custom_status(raw)

        if icon_char == "💬":
            subtitle = "💬  Lead with an emoji for a custom icon"
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
