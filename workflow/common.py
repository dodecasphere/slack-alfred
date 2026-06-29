#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta

CONFIG_FILE        = os.path.expanduser("~/.config/slack-alfred/config.json")
ICON_CACHE         = os.path.expanduser("~/.config/slack-alfred/icons")
USAGE_FILE         = os.path.expanduser("~/.config/slack-alfred/usage.json")
TOKEN_ERROR_FLAG   = os.path.expanduser("~/.config/slack-alfred/token_error")
CUSTOM_EMOJI_CACHE        = os.path.expanduser("~/.config/slack-alfred/custom_emoji.json")
CUSTOM_EMOJI_IMAGES_DONE  = os.path.expanduser("~/.config/slack-alfred/custom_emoji_images.done")
CURRENT_STATUS_CACHE      = os.path.expanduser("~/.config/slack-alfred/current_status.json")
RECENT_STATUSES_FILE      = os.path.expanduser("~/.config/slack-alfred/recent_statuses.json")
SCHEDULE_STATE_FILE       = os.path.expanduser("~/.config/slack-alfred/schedule_state.json")

_CURRENT_STATUS_TTL  = 60   # seconds
_RECENT_STATUSES_DAYS = 10

_EMOJI_LIST_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emoji.json")
_CUSTOM_EMOJI_TTL = 86400  # 24 hours

_AUTH_ERRORS    = {"invalid_auth", "token_revoked", "account_inactive", "not_authed"}

_SUBMENU_PREFIX = "» "
_REMOVE_SUFFIX  = " » remove"
_EDIT_INFIX     = "» edit"
_TOKEN_SUBMENU  = "Update Token"
_SCHED_EDIT_PREFIX = "@edit "

DEFAULT_STATUSES = [
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

_SLACK_CODE     = re.compile(r'(:[a-z0-9_+\-]+:)', re.IGNORECASE)
_BRACKET_TITLE  = re.compile(r'^\[([^\]]+)\]\s*')


# ── Icon cache ────────────────────────────────────────────────────────────────

def _icon_name(emoji_char):
    return "_".join(f"{ord(c):04X}" for c in emoji_char if ord(c) > 31)


def icon_path(emoji_char):
    if not emoji_char:
        return None
    # ── :slack_code: reference ────────────────────────────────────────────────
    if emoji_char.startswith(":") and emoji_char.endswith(":"):
        name = emoji_char[1:-1]
        for ext in (".png", ".gif", ".jpg"):
            p = os.path.join(ICON_CACHE, f"{name}{ext}")
            if os.path.exists(p):
                return p
        # Fall back to standard emoji Unicode char if available
        char = _load_standard_emoji().get(name)
        if char:
            return icon_path(char)
        return None
    # ── Unicode emoji ─────────────────────────────────────────────────────────
    path = os.path.join(ICON_CACHE, f"{_icon_name(emoji_char)}.png")
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


def cached_icon_path(emoji_char):
    """Like icon_path() but never spawns JXA — only returns a path if already cached."""
    if not emoji_char:
        return None
    if emoji_char.startswith(":") and emoji_char.endswith(":"):
        name = emoji_char[1:-1]
        for ext in (".png", ".gif", ".jpg"):
            p = os.path.join(ICON_CACHE, f"{name}{ext}")
            if os.path.exists(p):
                return p
        char = _load_standard_emoji().get(name)
        if char:
            return cached_icon_path(char)
        return None
    path = os.path.join(ICON_CACHE, f"{_icon_name(emoji_char)}.png")
    return path if os.path.exists(path) else None


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

    m = re.fullmatch(r'(\d+(?:\.\d+)?)\s*s(?:ec|ecs|econd|econds)?', t)
    if m:
        return int(float(m.group(1)))

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


def parse_expiry_token(text):
    """
    Parse a standalone expiry expression. Strips optional leading 'for'/'until'.
    Returns (expiry_ts, display, config_str) or (None, None, None).

    Bare integer ≤23 → nearest clock hour (time). Bare integer >23 → that many hours (duration).
    Otherwise format determines type: explicit h/m units → duration; am/pm/colon → time.
    """
    inner = re.sub(r'^(?:for|until)\s+', '', text.strip(), flags=re.IGNORECASE).strip()

    if re.fullmatch(r'\d+', inner):
        n = int(inner)
        if n <= 23:
            ts, time_label = parse_until_time(inner)
            if ts:
                return ts, f"expires at {time_label}", inner
        else:
            secs = n * 3600
            cfg = _fmt_duration(secs)
            return int(time.time()) + secs, f"expires in {cfg}", cfg
        return None, None, None

    secs = parse_duration(inner)
    if secs is not None:
        cfg = _fmt_duration(secs)
        return int(time.time()) + secs, f"expires in {cfg}", cfg

    ts, time_label = parse_until_time(inner)
    if ts:
        return ts, f"expires at {time_label}", inner

    return None, None, None


def extract_expiry(text):
    """
    Strip an expiry expression from the end of text. Accepts 'for <expr>',
    'until <expr>', or a bare expiry as the last 1-2 words.
    Returns (expiry_ts, expiry_display, expiry_config_str, clean_text).
    expiry_ts=0 means no expiry.
    """
    for pattern in (r'\bfor\s+(.+)$', r'\buntil\s+(.+)$'):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            ts, display, cfg = parse_expiry_token(m.group(1).strip())
            if ts is not None:
                return ts, display, cfg, text[:m.start()].strip()

    words = text.split()
    for n in (2, 1):
        if len(words) > n:
            ts, display, cfg = parse_expiry_token(" ".join(words[-n:]))
            if ts is not None:
                return ts, display, cfg, " ".join(words[:-n])

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


# ── Schedule parsing ────────────────────────────────────────────────────────────

_WEEKDAY_NAMES = {
    "mon": 0, "monday": 0, "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "weds": 2, "wednesday": 2, "thu": 3, "thur": 3, "thurs": 3,
    "thursday": 3, "fri": 4, "friday": 4, "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}
_DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _fmt_clock(hour, minute):
    ampm = "AM" if hour < 12 else "PM"
    h12  = hour % 12 or 12
    return f"{h12}:{minute:02d} {ampm}"


def parse_time_of_day(text):
    """
    Parse a clock time into (hour, minute, '9:00 AM'). Returns None if
    unrecognized. Strict: a bare integer with no am/pm and no colon is
    ambiguous and rejected (use '9am' or '09:00').
    """
    t = text.strip().lower()
    if t == "noon":
        return 12, 0, "12:00 PM"
    if t == "midnight":
        return 0, 0, "12:00 AM"

    m = re.fullmatch(r'(\d{1,2}):(\d{2})\s*(am?|pm?)?', t)
    if m:
        hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
    else:
        m = re.fullmatch(r'(\d{1,2})\s*(am|pm|a|p)', t)
        if not m:
            return None
        hour, minute, ampm = int(m.group(1)), 0, m.group(2)

    if ampm in ('pm', 'p') and hour != 12:
        hour += 12
    elif ampm in ('am', 'a') and hour == 12:
        hour = 0

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute, _fmt_clock(hour, minute)


def _parse_day_spec(text):
    """
    Split a leading recurring day spec from text.
    Returns (sorted_weekday_ints, remainder) or (None, text) if no day spec.
    """
    t = text.strip()
    low = t.lower()
    for kw, days in (("everyday", range(7)), ("every day", range(7)),
                     ("daily", range(7)),
                     ("weekdays", range(5)), ("weekday", range(5)),
                     ("weekends", [5, 6]), ("weekend", [5, 6])):
        if low == kw or low.startswith(kw + " "):
            return sorted(days), t[len(kw):].strip()

    tokens   = low.split()
    days     = []
    consumed = 0
    for tok in tokens:
        parts = [p for p in tok.split(",") if p]
        if parts and all(p in _WEEKDAY_NAMES for p in parts):
            days.extend(_WEEKDAY_NAMES[p] for p in parts)
            consumed += 1
        else:
            break
    if days:
        return sorted(set(days)), " ".join(t.split()[consumed:])
    return None, text


def _fmt_days(days):
    s = sorted(set(days))
    if s == list(range(7)):
        return "every day"
    if s == [0, 1, 2, 3, 4]:
        return "weekdays"
    if s == [5, 6]:
        return "weekends"
    return ", ".join(_DAY_ABBR[d] for d in s)


def parse_schedule_when(text, now=None):
    """
    Parse a schedule trigger expression into a normalized spec dict, or None.

    Recurring → {"kind":"recurring","days":[..],"hour","minute","desc"}
    One-off   → {"kind":"one_off","timestamp":unix,"desc"}

    Accepts recurring: 'weekdays 9am', 'daily 12:30pm', 'weekends 10am',
    'mon,wed,fri 5pm', 'tue thu 9:00'.
    Accepts one-off: 'in 2h', 'today 5pm', 'tomorrow 3pm', '2026-12-25 9am',
    or a bare time ('5pm') meaning the next occurrence.
    """
    now = now or datetime.now()
    t   = text.strip()
    low = t.lower()
    if not low:
        return None

    # one-off: in <duration>
    m = re.match(r'in\s+(.+)$', low)
    if m:
        secs = parse_duration(m.group(1).strip())
        if secs is None:
            return None
        dt = now + timedelta(seconds=secs)
        return {"kind": "one_off", "timestamp": int(dt.timestamp()),
                "desc": f"in {_fmt_duration(secs)}"}

    # one-off: today/tomorrow <time>
    m = re.match(r'(today|tomorrow)\s+(.+)$', low)
    if m:
        tod = parse_time_of_day(m.group(2).strip())
        if not tod:
            return None
        hour, minute, label = tod
        day = now.date() + (timedelta(days=1) if m.group(1) == "tomorrow"
                            else timedelta())
        dt  = datetime(day.year, day.month, day.day, hour, minute)
        return {"kind": "one_off", "timestamp": int(dt.timestamp()),
                "desc": f"{m.group(1)} at {label}"}

    # one-off: YYYY-MM-DD [time]
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})(?:\s+(.+))?$', low)
    if m:
        if m.group(4):
            tod = parse_time_of_day(m.group(4).strip())
            if not tod:
                return None
            hour, minute, label = tod
        else:
            hour, minute, label = 9, 0, "9:00 AM"
        try:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                          hour, minute)
        except ValueError:
            return None
        return {"kind": "one_off", "timestamp": int(dt.timestamp()),
                "desc": f"{dt.strftime('%b %-d')} at {label}"}

    # recurring: <day-spec> <time>
    days, rest = _parse_day_spec(low)
    if days is not None:
        tod = parse_time_of_day(rest.strip())
        if not tod:
            return None
        hour, minute, label = tod
        return {"kind": "recurring", "days": days, "hour": hour,
                "minute": minute, "desc": f"{_fmt_days(days)} at {label}"}

    # one-off: bare time → next occurrence
    ts, label = parse_until_time(low)
    if ts:
        return {"kind": "one_off", "timestamp": ts, "desc": f"at {label}"}

    return None


def evaluate_schedule(sched, now_dt, fired_keys, grace_seconds=300):
    """
    Decide what the dispatcher should do with one schedule at now_dt.

    Returns (action, occurrence_key):
      ("fire", key)  → set the status now and record key in fired state
      ("expire", None) → a one-off whose time passed beyond grace; drop it
      ("wait", None)   → not due, already fired, stale recurring, or disabled
    """
    if not sched.get("enabled", True):
        return ("wait", None)

    sid = sched.get("id", "")

    if sched.get("kind") == "one_off":
        ts    = sched.get("timestamp", 0)
        delta = now_dt.timestamp() - ts
        if delta < 0:
            return ("wait", None)
        if delta <= grace_seconds:
            return ("fire", f"{sid}@{ts}")
        return ("expire", None)

    if sched.get("kind") == "recurring":
        if now_dt.weekday() not in sched.get("days", []):
            return ("wait", None)
        key = f"{sid}@{now_dt.strftime('%Y-%m-%d')}"
        if key in fired_keys:
            return ("wait", None)
        sched_dt = now_dt.replace(hour=sched.get("hour", 0),
                                  minute=sched.get("minute", 0),
                                  second=0, microsecond=0)
        delta = now_dt.timestamp() - sched_dt.timestamp()
        if 0 <= delta <= grace_seconds:
            return ("fire", key)
        return ("wait", None)

    return ("wait", None)


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


def extract_bracket_title(raw):
    """Strip a leading [Title] from raw; return (title_or_None, remaining_raw)."""
    m = _BRACKET_TITLE.match(raw)
    if m:
        return m.group(1).strip(), raw[m.end():]
    return None, raw


def parse_custom_status(raw):
    """
    Parse free-form query into (menu_icon, slack_emoji, status_text,
                                expiry_ts, expiry_display, expiry_config).

    Leading codes follow a three-slot rule:
      slot 1 (icon)  — Unicode emoji OR first :code: → used as Alfred menu icon
      slot 2 (emoji) — second :code: (if present)   → sent to Slack as status emoji
      slot 3+ (text) — everything else               → status text

    '🧠 :brain: deep focus'              → ('🧠',      ':brain:',  'deep focus', ...)
    '🏋️ at the gym'                      → ('🏋️',      '🏋️',       'at the gym', ...)
    ':school: Going to school'           → (':school:', ':school:', 'Going to school', ...)
    ':custom: :headphones: On a call'    → (':custom:', ':headphones:', 'On a call', ...)
    ':custom: :hphone: :brain: focus'    → (':custom:', ':hphone:',    ':brain: focus', ...)
    'be right back'                      → ('💬',       ':speech_balloon:', 'be right back', ...)
    """
    icon_char, rest = split_emoji_prefix(raw)

    if not icon_char:
        # No leading Unicode emoji — check for a leading :slack_code:
        m = _SLACK_CODE.match(raw.strip())
        if m:
            icon_char   = m.group(1)
            remaining   = raw.strip()[m.end():].strip()
            # Second :code: (if present) becomes the Slack emoji
            m2 = _SLACK_CODE.match(remaining)
            if m2:
                slack_emoji = m2.group(1)
                remaining   = remaining[m2.end():].strip()
            else:
                slack_emoji = icon_char
            ts, display, cfg, clean = extract_expiry(remaining)
            return icon_char, slack_emoji, clean, ts, display, cfg
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


# ── Submenus ──────────────────────────────────────────────────────────────────

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
    sub       = f"{emoji}  {text}" if emoji else text

    expiry_ts, _ = compute_expiry_from_config(preset.get("expiry", ""))

    def make_args(ts, cfg):
        base = {"text": text, "emoji": emoji, "icon": icon_char,
                "expiry": ts, "expiry_config": cfg, "title": preset_title}
        return json.dumps(base), json.dumps({"action": "update_preset", **base})

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
            "title":         preset_title,
        }),
        "valid": True,
    }, icon_char)

    # ── Fixed duration items ─────────────────────────────────────────────────
    def expiry_item(label, secs):
        cfg             = _fmt_duration(secs)
        ts              = int(time.time()) + secs
        arg_set, arg_save = make_args(ts, cfg)
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
        ts, disp, cfg = parse_expiry_token(custom)
        if ts is not None:
            label             = "Expire" + disp[len("expires"):]
            arg_set, arg_save = make_args(ts, cfg)
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

    # ── Edit preset ──────────────────────────────────────────────────────────
    edit_item = with_icon({
        "title":        "Edit preset…",
        "subtitle":     f"Change title, emoji, or text",
        "autocomplete": f"{_SUBMENU_PREFIX}{preset_title} {_EDIT_INFIX} {_preset_prefill(preset)}",
        "valid":        False,
    }, "✏️")

    # ── Remove preset (last item) ────────────────────────────────────────────
    remove_item = with_icon({
        "title":        "Remove preset",
        "subtitle":     f"Delete '{preset_title}' from saved presets",
        "autocomplete": f"{_SUBMENU_PREFIX}{preset_title}{_REMOVE_SUFFIX}",
        "valid":        False,
    }, "❌")

    return [set_item] + duration_items + [custom_item, edit_item, remove_item]


def _preset_prefill(preset):
    """Build the pre-filled edit string for a preset: '[title] icon emoji text'."""
    title     = preset["title"]
    icon_char = preset.get("icon", "")
    emoji     = preset["emoji"]
    text      = preset["text"]
    if icon_char and icon_char != emoji:
        return f"[{title}] {icon_char} {emoji} {text}"
    return f"[{title}] {emoji} {text}"


def build_edit_submenu(preset_title, edit_query, statuses):
    preset = next((s for s in statuses if s["title"] == preset_title), None)
    if not preset:
        return [{"title": f"Preset not found: {preset_title!r}", "valid": False}]

    if not edit_query:
        return [with_icon({
            "title":        "Edit preset…",
            "subtitle":     "Tab to edit title, emoji, and text",
            "autocomplete": f"{_SUBMENU_PREFIX}{preset_title} {_EDIT_INFIX} {_preset_prefill(preset)}",
            "valid":        False,
        }, "✏️")]

    bracket_title, raw_for_parse = extract_bracket_title(edit_query)
    icon_char, slack_emoji, text, _, _, _ = parse_custom_status(raw_for_parse)

    if not text:
        return [with_icon({
            "title":   "Type the new status text",
            "subtitle": "e.g. [New Title] :emoji: New text",
            "valid":    False,
        }, "✏️")]

    arg = {"action": "edit_preset", "title": preset_title,
           "text": text, "emoji": slack_emoji, "icon": icon_char}
    if bracket_title:
        arg["new_title"] = bracket_title

    display_title = bracket_title or preset_title
    sub = f"{slack_emoji}  {text}" if slack_emoji else text
    return [with_icon({
        "title":    f"Save \"{display_title}\"",
        "subtitle": sub,
        "arg":      json.dumps(arg),
        "valid":    True,
    }, "✏️")]


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


def build_token_submenu(token_input):
    if not token_input:
        return [{"title": "Paste your xoxp- token here",
                 "subtitle": "Type or paste your Slack user OAuth token",
                 "valid": False}]
    if re.match(r'^xoxp-\S+', token_input):
        display = token_input[:14] + "…" if len(token_input) > 18 else token_input
        return [{"title": f"Save token: {display}",
                 "subtitle": "Saves the token to local config",
                 "arg": json.dumps({"action": "save_token", "token": token_input}),
                 "valid": True}]
    return [{"title": "Token not recognized",
             "subtitle": "Should start with xoxp-",
             "valid": False}]


# ── Token management ──────────────────────────────────────────────────────────

def set_token_error_flag():
    try:
        os.makedirs(os.path.dirname(TOKEN_ERROR_FLAG), exist_ok=True)
        open(TOKEN_ERROR_FLAG, "w").close()
    except Exception:
        pass


def clear_token_error_flag():
    try:
        os.remove(TOKEN_ERROR_FLAG)
    except FileNotFoundError:
        pass


# ── Usage tracking ────────────────────────────────────────────────────────────

def load_usage():
    try:
        with open(USAGE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _usage_score(entry):
    count = entry.get("count", 0)
    if not count:
        return 0.0
    days_since = (time.time() - entry.get("last_used", 0)) / 86400
    recency = 1.0 / (1.0 + days_since / 14)
    return count * 3.0 + recency


def record_usage(title):
    if not title:
        return
    usage = load_usage()
    entry = usage.get(title, {"count": 0, "last_used": 0})
    entry["count"] += 1
    entry["last_used"] = int(time.time())
    usage[title] = entry
    try:
        with open(USAGE_FILE, "w") as f:
            json.dump(usage, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except Exception:
        pass


# ── Emoji search ─────────────────────────────────────────────────────────────

def _load_standard_emoji():
    try:
        with open(_EMOJI_LIST_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _load_custom_emoji():
    """Load cached custom emoji, firing an async refresh if the cache is stale."""
    try:
        with open(CUSTOM_EMOJI_CACHE) as f:
            cache = json.load(f)
        if time.time() - cache.get("fetched_at", 0) > _CUSTOM_EMOJI_TTL:
            _refresh_custom_emoji_async()
        return cache.get("emoji", {})
    except (FileNotFoundError, json.JSONDecodeError):
        _refresh_custom_emoji_async()
        return {}


def _refresh_custom_emoji_async():
    fetch_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetch_emoji.py")
    subprocess.Popen([sys.executable, fetch_script],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def search_emoji(fragment):
    """
    Return all emoji codes matching fragment. Prefix matches come first,
    then substring matches (e.g. 'ea' matches ':eating:' then ':beachball:').
    Standard emoji precede custom within each group.
    """
    frag     = fragment.lower()
    standard = _load_standard_emoji()
    custom   = _load_custom_emoji()

    prefix_std = []
    substr_std = []
    prefix_cus = []
    substr_cus = []

    for code in sorted(standard):
        if code.startswith(frag):
            prefix_std.append((code, standard[code]))
        elif frag in code:
            substr_std.append((code, standard[code]))

    for code in sorted(custom):
        if code.startswith(frag):
            prefix_cus.append((code, None))
        elif frag in code:
            substr_cus.append((code, None))

    return prefix_std + prefix_cus + substr_std + substr_cus


# ── Setup ─────────────────────────────────────────────────────────────────────

SETUP_URL = "https://api.slack.com/apps"


def do_setup():
    subprocess.run(["open", SETUP_URL])
    steps = (
        "1. Create a new Slack app at api.slack.com/apps\\n"
        "2. From scratch → name it, pick your workspace\\n"
        "3. OAuth & Permissions → User Token Scopes → add: users.profile:write  users:write  emoji:read\\n"
        "4. Install to Workspace → copy the xoxp- token\\n"
        "5. Return to Alfred → Tab this item → paste your token"
    )
    script = (
        f'display dialog "Slack Status Setter — Setup\\n\\n{steps}" '
        f'with title "Slack Status Setup" '
        f'buttons {{"OK"}} default button "OK"'
    )
    subprocess.Popen(["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def build_setup_item():
    return with_icon({
        "title":        "Setup Required — Press Enter",
        "subtitle":     "Opens Slack API page to generate your token · Tab to enter it",
        "arg":          "setup",
        "autocomplete": f"{_SUBMENU_PREFIX}{_TOKEN_SUBMENU} ",
        "valid":        True,
    }, "⚙️")


def build_token_error_item():
    return {
        "title":        "⚠️ Token invalid — Tab to update",
        "subtitle":     "Slack rejected your token. Tab to paste a new one.",
        "autocomplete": f"{_SUBMENU_PREFIX}{_TOKEN_SUBMENU} ",
        "valid":        False,
    }


# ── Recent statuses ───────────────────────────────────────────────────────────

def format_relative_time(ts):
    diff = time.time() - ts
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{int(diff // 60)}m ago"
    if diff < 86400:
        return f"{int(diff // 3600)}h ago"
    days = int(diff // 86400)
    return "yesterday" if days == 1 else f"{days} days ago"


def load_recent_statuses():
    try:
        with open(RECENT_STATUSES_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def record_recent_status(text, emoji, icon, expiry_config):
    cutoff = time.time() - _RECENT_STATUSES_DAYS * 86400
    recent = load_recent_statuses()
    recent = [r for r in recent
              if not (r["text"] == text and r["emoji"] == emoji)
              and r.get("set_at", 0) > cutoff]
    entry  = {"text": text, "emoji": emoji, "icon": icon,
              "expiry_config": expiry_config, "set_at": time.time()}
    recent = [entry] + recent
    try:
        os.makedirs(os.path.dirname(RECENT_STATUSES_FILE), exist_ok=True)
        with open(RECENT_STATUSES_FILE, "w") as f:
            json.dump(recent, f)
    except Exception:
        pass


def build_recent_status_items(statuses):
    cutoff = time.time() - _RECENT_STATUSES_DAYS * 86400
    recent = load_recent_statuses()
    preset_keys = {(s["text"], s["emoji"]) for s in statuses}
    recent = [r for r in recent
              if (r["text"], r["emoji"]) not in preset_keys
              and r.get("set_at", 0) > cutoff]
    if not recent:
        return []

    items = []
    for r in recent:
        text         = r["text"]
        emoji        = r["emoji"]
        icon         = r.get("icon", "")
        expiry_cfg   = r.get("expiry_config", "")
        expiry_ts, _ = compute_expiry_from_config(expiry_cfg)
        rel_time     = format_relative_time(r["set_at"])
        subtitle     = f"{emoji}  {text} · Set {rel_time} · ⌘↩ to save as preset"

        set_arg  = json.dumps({"text": text, "emoji": emoji, "icon": icon,
                               "expiry": expiry_ts, "expiry_config": expiry_cfg})
        save_arg = json.dumps({"text": text, "emoji": emoji, "icon": icon,
                               "expiry": expiry_ts, "expiry_config": expiry_cfg,
                               "action": "save_preset"})
        items.append(with_icon({
            "title":    text,
            "subtitle": subtitle,
            "arg":      set_arg,
            "valid":    True,
            "mods": {"cmd": {
                "subtitle": "Save as preset",
                "arg":      save_arg,
                "valid":    True,
            }},
        }, icon or emoji))
    return items


# ── Current status cache ──────────────────────────────────────────────────────

def format_expiry_countdown(expiration_ts):
    if not expiration_ts:
        return ""
    remaining = expiration_ts - time.time()
    if remaining <= 0:
        return "clearing…"
    if remaining < 60:
        return f"expires in {int(remaining)}s"
    if remaining < 3600:
        return f"expires in {int(remaining // 60)}m"
    hours = int(remaining // 3600)
    mins  = int((remaining % 3600) // 60)
    return f"expires in {hours}h {mins}m" if mins else f"expires in {hours}h"


def load_current_status_cache():
    try:
        with open(CURRENT_STATUS_CACHE) as f:
            data = json.load(f)
        if time.time() - data.get("fetched_at", 0) > _CURRENT_STATUS_TTL:
            return None
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_current_status_cache(text, emoji, expiration):
    data = {
        "status_text":       text,
        "status_emoji":      emoji,
        "status_expiration": expiration,
        "fetched_at":        time.time(),
    }
    try:
        os.makedirs(os.path.dirname(CURRENT_STATUS_CACHE), exist_ok=True)
        with open(CURRENT_STATUS_CACHE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def _current_status_needs_rerun():
    """True only for sub-60s expiry countdown. Loading state is static to avoid refocus."""
    cache = load_current_status_cache()
    if cache is None:
        return False
    expiration = cache.get("status_expiration", 0)
    if expiration:
        remaining = expiration - time.time()
        if 0 < remaining < 60:
            return True
    return False


def _fetch_current_status_async(token):
    fetch_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetch_status.py")
    subprocess.Popen([sys.executable, fetch_script, token],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def build_current_status_item(token):
    cache = load_current_status_cache()

    clear_arg = json.dumps({"text": "", "emoji": "", "icon": "", "expiry": 0, "expiry_config": ""})

    if cache is None:
        if token:
            _fetch_current_status_async(token)
        # Clearing is safe regardless of the (still-loading) current status, so
        # offer ⌘↩ to clear immediately rather than forcing a wait for the fetch.
        return with_icon({
            "title":    "Fetching status…",
            "subtitle": "Current Slack status loading · ⌘↩ to clear",
            "valid":    False,
            "mods": {"cmd": {
                "subtitle": "Clear status",
                "arg":      clear_arg,
                "valid":    True,
            }},
        }, "💬")

    text       = cache.get("status_text", "")
    emoji      = cache.get("status_emoji", "")
    expiration = cache.get("status_expiration", 0)

    if not text:
        return with_icon({
            "title":    "No status set",
            "subtitle": "",
            "valid":    False,
        }, "💬")

    expiry_str  = format_expiry_countdown(expiration)
    subtitle    = f"{expiry_str} · ⌘↩ to clear" if expiry_str else "⌘↩ to clear"
    return with_icon({
        "title":    f"Current status: {text}",
        "subtitle": subtitle,
        "valid":    False,
        "mods": {"cmd": {
            "subtitle": "Clear status",
            "arg":      clear_arg,
            "valid":    True,
        }},
    }, emoji or "💬")


# ── Config ────────────────────────────────────────────────────────────────────

def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ── Slack API ───────────────────────────────────────────────────────────────────

def set_slack_status(token, text, emoji, expiry=0):
    """POST users.profile.set. Returns the parsed JSON response."""
    payload = json.dumps({
        "profile": {
            "status_text":       text,
            "status_emoji":      emoji,
            "status_expiration": expiry,
        }
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://slack.com/api/users.profile.set",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json; charset=utf-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── Schedules ────────────────────────────────────────────────────────────────────

def load_schedule_state():
    try:
        with open(SCHEDULE_STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"fired": {}}


def save_schedule_state(state):
    try:
        os.makedirs(os.path.dirname(SCHEDULE_STATE_FILE), exist_ok=True)
        with open(SCHEDULE_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def build_schedule_create_items(status_part, when_part):
    """Live preview for 'slacks <status> @ <when>'. Returns Alfred items."""
    icon_char, slack_emoji, text, _ts, _disp, expiry_cfg = parse_custom_status(status_part)

    if not text:
        return [{"title": "Type a status before @",
                 "subtitle": "e.g. 🎧 Focusing @ weekdays 9am",
                 "valid": False}]

    spec = parse_schedule_when(when_part) if when_part else None
    if not spec:
        return [with_icon({
            "title":    f'Schedule "{text}"',
            "subtitle": "Type a time after @ — e.g. weekdays 9am, tomorrow 3pm, in 2h",
            "valid":    False,
        }, icon_char)]

    subtitle = f"{slack_emoji}  {spec['desc']}"
    if expiry_cfg:
        _, exp_disp = compute_expiry_from_config(expiry_cfg)
        if exp_disp:
            subtitle += f" · clears {exp_disp.replace('expires ', '')}"

    arg = json.dumps({
        "action":        "save_schedule",
        "when_raw":      when_part,
        "text":          text,
        "emoji":         slack_emoji,
        "icon":          icon_char,
        "expiry_config": expiry_cfg,
    })
    return [with_icon({
        "title":    f'Schedule "{text}" · {spec["desc"]}',
        "subtitle": subtitle,
        "arg":      arg,
        "valid":    True,
    }, icon_char)]


def _days_to_token(days):
    """Inverse of _parse_day_spec: weekday ints → a re-parseable token."""
    s = sorted(set(days))
    if s == list(range(7)):
        return "daily"
    if s == [0, 1, 2, 3, 4]:
        return "weekdays"
    if s == [5, 6]:
        return "weekends"
    abbr = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    return ",".join(abbr[d] for d in s)


def _schedule_to_query(sched):
    """Reconstruct a re-parseable '<status> @ <when>' string for editing."""
    icon  = sched.get("icon", "")
    emoji = sched.get("emoji", "")
    text  = sched.get("text", "")
    status = f"{icon} {emoji} {text}" if icon and icon != emoji else f"{emoji} {text}"
    status = status.strip()
    if sched.get("expiry"):
        status += f" for {sched['expiry']}"

    if sched.get("kind") == "one_off":
        when = datetime.fromtimestamp(sched.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M")
    else:
        when = f"{_days_to_token(sched.get('days', []))} " \
               f"{sched.get('hour', 0):02d}:{sched.get('minute', 0):02d}"
    return f"{status} @ {when}"


def build_schedule_edit_items(edit_query):
    """Preview for '@edit <id> <status> @ <when>'. Returns Alfred items."""
    parts = edit_query.strip().split(None, 1)
    if not parts:
        return [{"title": "Editing schedule…", "valid": False}]
    sid  = parts[0]
    body = parts[1] if len(parts) > 1 else ""

    status_part, _, when_part = body.partition("@")
    items = build_schedule_create_items(status_part.strip(), when_part.strip())

    # Re-target the create preview as an in-place update.
    for it in items:
        if it.get("valid") and it.get("arg"):
            arg = json.loads(it["arg"])
            arg["action"] = "edit_schedule"
            arg["id"]     = sid
            it["arg"]     = json.dumps(arg)
            it["title"]   = it["title"].replace('Schedule "', 'Update "', 1)
    return items


def build_schedule_list_items(config):
    """List existing schedules with edit / toggle / delete / run-now actions."""
    schedules = config.get("schedules", [])
    if not schedules:
        return [{"title": "No schedules yet",
                 "subtitle": "Type a status then @ a time — e.g. 🎧 Focusing @ weekdays 9am",
                 "valid": False}]

    items = []
    for s in schedules:
        enabled = s.get("enabled", True)
        text    = s.get("text", "")
        icon    = s.get("icon", "")
        state   = "on" if enabled else "paused"
        toggle_label = "pause" if enabled else "resume"

        subtitle = (f"{s.get('emoji', '')}  {s.get('desc', '')} · {state} · "
                    f"⇥ edit · ⏎ {toggle_label} · ⌘ delete · ⌥ run now")

        run_arg = json.dumps({
            "text":          text,
            "emoji":         s.get("emoji", ""),
            "icon":          icon,
            "expiry":        compute_expiry_from_config(s.get("expiry", ""))[0],
            "expiry_config": s.get("expiry", ""),
        })
        items.append(with_icon({
            "title":        f'{text}  ({s.get("desc", "")})',
            "subtitle":     subtitle,
            "autocomplete": f"{_SCHED_EDIT_PREFIX}{s.get('id', '')} {_schedule_to_query(s)}",
            "arg":          json.dumps({"action": "toggle_schedule", "id": s.get("id", "")}),
            "valid":        True,
            "mods": {
                "cmd": {"subtitle": f"Delete schedule: {text}",
                        "arg": json.dumps({"action": "remove_schedule", "id": s.get("id", "")}),
                        "valid": True},
                "alt": {"subtitle": f"Set now: {text}",
                        "arg": run_arg, "valid": True},
            },
        }, icon))
    return items
