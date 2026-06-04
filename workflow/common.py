#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta

CONFIG_FILE        = os.path.expanduser("~/.config/slack-alfred/config.json")
ICON_CACHE         = os.path.expanduser("~/.config/slack-alfred/icons")
USAGE_FILE         = os.path.expanduser("~/.config/slack-alfred/usage.json")
TOKEN_ERROR_FLAG   = os.path.expanduser("~/.config/slack-alfred/token_error")
CUSTOM_EMOJI_CACHE        = os.path.expanduser("~/.config/slack-alfred/custom_emoji.json")
CUSTOM_EMOJI_IMAGES_DONE  = os.path.expanduser("~/.config/slack-alfred/custom_emoji_images.done")
CURRENT_STATUS_CACHE      = os.path.expanduser("~/.config/slack-alfred/current_status.json")

_CURRENT_STATUS_TTL = 60  # seconds

_EMOJI_LIST_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emoji.json")
_CUSTOM_EMOJI_TTL = 86400  # 24 hours

_AUTH_ERRORS    = {"invalid_auth", "token_revoked", "account_inactive", "not_authed"}

_SUBMENU_PREFIX = "» "
_REMOVE_SUFFIX  = " » remove"
_EDIT_INFIX     = "» edit"
_TOKEN_SUBMENU  = "Update Token"

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


def _fetch_current_status_async(token):
    fetch_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetch_status.py")
    subprocess.Popen([sys.executable, fetch_script, token],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def build_current_status_item(token):
    cache = load_current_status_cache()

    if cache is None:
        if token:
            _fetch_current_status_async(token)
        return with_icon({
            "title":    "Fetching status…",
            "subtitle": "Current Slack status loading",
            "valid":    False,
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
    clear_arg   = json.dumps({"text": "", "emoji": "", "icon": "", "expiry": 0, "expiry_config": ""})
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
