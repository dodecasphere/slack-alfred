#!/usr/bin/env python3
"""
Tests for the pure parsing functions in workflow/filter.py.

Run with:  python3 -m unittest discover tests
       or: python3 tests/test_parsing.py
"""
import importlib.util
import json
import os
import sys
import time
import unittest
from unittest import mock

# Load workflow/filter.py under the name "workflow_filter" to avoid shadowing
# Python's built-in filter() function.
_spec = importlib.util.spec_from_file_location(
    "common",
    os.path.join(os.path.dirname(__file__), "..", "workflow", "common.py"),
)
wf = importlib.util.module_from_spec(_spec)
sys.modules["common"] = wf
_spec.loader.exec_module(wf)

FIXED_TIME = 1_000_000  # frozen epoch used wherever time.time() is mocked


def _with_time(fn, *args):
    """Call fn(*args) with time.time() frozen to FIXED_TIME."""
    with mock.patch("common.time") as mt:
        mt.time.return_value = FIXED_TIME
        return fn(*args)


# ── parse_duration ────────────────────────────────────────────────────────────

class TestParseDuration(unittest.TestCase):

    def test_hours(self):
        self.assertEqual(wf.parse_duration("2h"),      7200)
        self.assertEqual(wf.parse_duration("1hr"),     3600)
        self.assertEqual(wf.parse_duration("1.5h"),    5400)
        self.assertEqual(wf.parse_duration("2hour"),   7200)
        self.assertEqual(wf.parse_duration("2hours"),  7200)

    def test_minutes(self):
        self.assertEqual(wf.parse_duration("30m"),        1800)
        self.assertEqual(wf.parse_duration("30min"),      1800)
        self.assertEqual(wf.parse_duration("30mins"),     1800)
        self.assertEqual(wf.parse_duration("30minutes"),  1800)

    def test_combined(self):
        self.assertEqual(wf.parse_duration("1h30m"),   5400)
        self.assertEqual(wf.parse_duration("1h 30m"),  5400)
        self.assertEqual(wf.parse_duration("2h15m"),   8100)

    def test_bare_integer_not_parsed(self):
        # bare integers are handled by parse_expiry_token, not here
        self.assertIsNone(wf.parse_duration("30"))
        self.assertIsNone(wf.parse_duration("5"))

    def test_seconds(self):
        self.assertEqual(wf.parse_duration("60s"),        60)
        self.assertEqual(wf.parse_duration("30sec"),      30)
        self.assertEqual(wf.parse_duration("45secs"),     45)
        self.assertEqual(wf.parse_duration("90second"),   90)
        self.assertEqual(wf.parse_duration("10seconds"),  10)

    def test_invalid(self):
        self.assertIsNone(wf.parse_duration(""))
        self.assertIsNone(wf.parse_duration("foo"))
        self.assertIsNone(wf.parse_duration("5pm"))


# ── parse_until_time ──────────────────────────────────────────────────────────

class TestParseUntilTime(unittest.TestCase):

    def test_explicit_am_pm(self):
        _, label = wf.parse_until_time("5pm");   self.assertEqual(label, "5:00 PM")
        _, label = wf.parse_until_time("9am");   self.assertEqual(label, "9:00 AM")
        _, label = wf.parse_until_time("12pm");  self.assertEqual(label, "12:00 PM")
        _, label = wf.parse_until_time("12am");  self.assertEqual(label, "12:00 AM")

    def test_24h(self):
        _, label = wf.parse_until_time("17:00");  self.assertEqual(label, "5:00 PM")
        _, label = wf.parse_until_time("21:00");  self.assertEqual(label, "9:00 PM")

    def test_with_minutes(self):
        _, label = wf.parse_until_time("5:30pm");  self.assertEqual(label, "5:30 PM")
        _, label = wf.parse_until_time("14:45");   self.assertEqual(label, "2:45 PM")

    def test_keywords(self):
        _, label = wf.parse_until_time("noon");      self.assertEqual(label, "12:00 PM")
        _, label = wf.parse_until_time("midnight");  self.assertEqual(label, "12:00 AM")

    def test_timestamp_is_future(self):
        ts, _ = wf.parse_until_time("5pm")
        self.assertGreater(ts, 0)

    def test_invalid(self):
        self.assertEqual(wf.parse_until_time("foo"),    (None, None))
        self.assertEqual(wf.parse_until_time("25:00"),  (None, None))
        self.assertEqual(wf.parse_until_time(""),       (None, None))


# ── parse_expiry_token ────────────────────────────────────────────────────────

class TestParseExpiryToken(unittest.TestCase):

    def _t(self, text):
        return _with_time(wf.parse_expiry_token, text)

    # Duration — explicit units
    def test_duration_bare(self):
        ts, display, cfg = self._t("2h")
        self.assertEqual(ts, FIXED_TIME + 7200)
        self.assertEqual(display, "expires in 2h")
        self.assertEqual(cfg, "2h")

    def test_duration_for_prefix(self):
        ts, display, cfg = self._t("for 2h")
        self.assertEqual(ts, FIXED_TIME + 7200)
        self.assertEqual(cfg, "2h")

    def test_until_with_duration_format_wins(self):
        # "until 2h" — format (explicit units) determines type, not keyword
        ts, display, cfg = self._t("until 2h")
        self.assertEqual(display, "expires in 2h")

    def test_duration_minutes(self):
        ts, display, cfg = self._t("30m")
        self.assertEqual(ts, FIXED_TIME + 1800)
        self.assertEqual(cfg, "30m")

    # Time — am/pm/colon patterns
    def test_time_bare(self):
        _, display, cfg = self._t("5pm")
        self.assertEqual(display, "expires at 5:00 PM")

    def test_time_until_prefix(self):
        _, display, _ = self._t("until 5pm")
        self.assertEqual(display, "expires at 5:00 PM")

    def test_for_with_time_format_wins(self):
        # "for 5pm" — format (am/pm) wins over "for" suggesting duration
        _, display, _ = self._t("for 5pm")
        self.assertEqual(display, "expires at 5:00 PM")

    def test_time_24h(self):
        _, display, _ = self._t("17:00")
        self.assertEqual(display, "expires at 5:00 PM")

    # Bare integers
    def test_bare_int_le_23_is_time(self):
        _, display, cfg = self._t("5")
        self.assertIn("expires at", display)
        self.assertEqual(cfg, "5")

    def test_bare_int_23_boundary_is_time(self):
        _, display, cfg = self._t("23")
        self.assertIn("expires at", display)
        self.assertIn("11:00 PM", display)

    def test_bare_int_24_is_hours(self):
        ts, display, cfg = self._t("24")
        self.assertEqual(ts, FIXED_TIME + 24 * 3600)
        self.assertEqual(display, "expires in 24h")
        self.assertEqual(cfg, "24h")

    def test_bare_int_gt_23_is_hours(self):
        ts, display, cfg = self._t("48")
        self.assertEqual(ts, FIXED_TIME + 48 * 3600)

    # Invalid
    def test_invalid(self):
        ts, display, cfg = self._t("blah")
        self.assertIsNone(ts)
        self.assertIsNone(display)
        self.assertIsNone(cfg)


# ── extract_expiry ────────────────────────────────────────────────────────────

class TestExtractExpiry(unittest.TestCase):

    def _e(self, text):
        return _with_time(wf.extract_expiry, text)

    # Explicit keywords
    def test_for_duration(self):
        ts, display, cfg, clean = self._e("focusing for 2h")
        self.assertEqual(clean, "focusing")
        self.assertEqual(display, "expires in 2h")

    def test_until_time(self):
        _, display, _, clean = self._e("focusing until 5pm")
        self.assertEqual(clean, "focusing")
        self.assertIn("5:00 PM", display)

    def test_for_time_format_wins(self):
        _, display, _, clean = self._e("focusing for 5pm")
        self.assertEqual(clean, "focusing")
        self.assertIn("5:00 PM", display)

    def test_until_duration_format_wins(self):
        _, display, _, clean = self._e("focusing until 2h")
        self.assertEqual(clean, "focusing")
        self.assertEqual(display, "expires in 2h")

    # Bare trailing expiry (no keyword)
    def test_bare_duration(self):
        ts, display, cfg, clean = self._e("focusing 2h")
        self.assertEqual(clean, "focusing")
        self.assertEqual(display, "expires in 2h")

    def test_bare_time(self):
        _, display, _, clean = self._e("focusing 5pm")
        self.assertEqual(clean, "focusing")
        self.assertIn("5:00 PM", display)

    def test_bare_int_le_23(self):
        _, display, _, clean = self._e("meeting 5")
        self.assertEqual(clean, "meeting")
        self.assertIn("expires at", display)

    def test_bare_int_gt_23(self):
        ts, display, cfg, clean = self._e("meeting 24")
        self.assertEqual(clean, "meeting")
        self.assertEqual(display, "expires in 24h")

    def test_two_word_time(self):
        _, display, _, clean = self._e("break 5 pm")
        self.assertEqual(clean, "break")
        self.assertIn("5:00 PM", display)

    # No expiry
    def test_no_expiry(self):
        ts, display, cfg, clean = self._e("on a call")
        self.assertEqual(ts, 0)
        self.assertEqual(clean, "on a call")

    def test_single_word_no_expiry(self):
        # A lone word can't be stripped as expiry — nothing would remain
        ts, _, _, clean = self._e("focusing")
        self.assertEqual(ts, 0)
        self.assertEqual(clean, "focusing")

    def test_two_words_not_expiry(self):
        ts, _, _, clean = self._e("be back")
        self.assertEqual(ts, 0)
        self.assertEqual(clean, "be back")


# ── parse_custom_status ───────────────────────────────────────────────────────

class TestParseCustomStatus(unittest.TestCase):

    def _cs(self, text):
        return _with_time(wf.parse_custom_status, text)

    def test_plain_text(self):
        icon, emoji, text, ts, display, cfg = self._cs("be right back")
        self.assertEqual(icon, "💬")
        self.assertEqual(emoji, ":speech_balloon:")
        self.assertEqual(text, "be right back")
        self.assertEqual(ts, 0)

    def test_leading_emoji_icon(self):
        icon, emoji, text, ts, display, cfg = self._cs("🏋️ at the gym")
        self.assertEqual(icon, "🏋️")
        self.assertEqual(emoji, "🏋️")
        self.assertEqual(text, "at the gym")

    def test_leading_slack_code(self):
        icon, emoji, text, ts, display, cfg = self._cs(":school: Going to school")
        self.assertEqual(icon, ":school:")
        self.assertEqual(emoji, ":school:")
        self.assertEqual(text, "Going to school")

    def test_leading_two_slack_codes(self):
        icon, emoji, text, ts, display, cfg = self._cs(":custom: :headphones: On a call")
        self.assertEqual(icon, ":custom:")
        self.assertEqual(emoji, ":headphones:")
        self.assertEqual(text, "On a call")

    def test_leading_three_slack_codes(self):
        icon, emoji, text, ts, display, cfg = self._cs(":custom: :headphones: :brain: focus")
        self.assertEqual(icon, ":custom:")
        self.assertEqual(emoji, ":headphones:")
        self.assertEqual(text, ":brain: focus")

    def test_emoji_with_inline_slack_code(self):
        icon, emoji, text, ts, display, cfg = self._cs("🧠 :brain: deep focus")
        self.assertEqual(icon, "🧠")
        self.assertEqual(emoji, ":brain:")
        self.assertEqual(text, "deep focus")

    def test_emoji_with_bare_duration(self):
        icon, emoji, text, ts, display, cfg = self._cs("🧠 deep focus 2h")
        self.assertEqual(text, "deep focus")
        self.assertEqual(display, "expires in 2h")

    def test_emoji_with_for_duration(self):
        _, _, text, _, display, _ = self._cs("🧠 deep focus for 2h")
        self.assertEqual(text, "deep focus")
        self.assertEqual(display, "expires in 2h")

    def test_emoji_with_until_time(self):
        _, _, text, _, display, _ = self._cs("🏋️ at the gym until 5pm")
        self.assertEqual(text, "at the gym")
        self.assertIn("5:00 PM", display)

    def test_no_expiry_when_no_trailing_token(self):
        _, _, text, ts, display, _ = self._cs("🧠 deep focus")
        self.assertEqual(text, "deep focus")
        self.assertEqual(ts, 0)
        self.assertEqual(display, "")


# ── extract_bracket_title ─────────────────────────────────────────────────────

class TestExtractBracketTitle(unittest.TestCase):

    def test_leading_bracket_extracted(self):
        title, rest = wf.extract_bracket_title("[Beach day] :beach_with_umbrella: at the beach")
        self.assertEqual(title, "Beach day")
        self.assertEqual(rest, ":beach_with_umbrella: at the beach")

    def test_no_bracket_returns_none(self):
        title, rest = wf.extract_bracket_title(":headphones: focusing")
        self.assertIsNone(title)
        self.assertEqual(rest, ":headphones: focusing")

    def test_bracket_title_trimmed(self):
        title, rest = wf.extract_bracket_title("[  My Title  ] some text")
        self.assertEqual(title, "My Title")
        self.assertEqual(rest, "some text")

    def test_bracket_not_at_start_ignored(self):
        title, rest = wf.extract_bracket_title("some [Title] text")
        self.assertIsNone(title)
        self.assertEqual(rest, "some [Title] text")

    def test_empty_bracket_not_extracted(self):
        title, rest = wf.extract_bracket_title("[] some text")
        self.assertIsNone(title)

    def test_bracket_with_expiry_in_rest(self):
        title, rest = wf.extract_bracket_title("[Focus block] :brain: deep work 2h")
        self.assertEqual(title, "Focus block")
        self.assertEqual(rest, ":brain: deep work 2h")

    def test_parse_custom_status_after_bracket_strip(self):
        _, raw = wf.extract_bracket_title("[My Status] :headphones: focusing for 2h")
        icon, emoji, text, ts, display, cfg = _with_time(wf.parse_custom_status, raw)
        self.assertEqual(icon, ":headphones:")
        self.assertEqual(emoji, ":headphones:")
        self.assertEqual(text, "focusing")
        self.assertEqual(display, "expires in 2h")


# ── _usage_score ──────────────────────────────────────────────────────────────

class TestUsageScore(unittest.TestCase):

    def test_unused_is_zero(self):
        self.assertEqual(wf._usage_score({}), 0.0)
        self.assertEqual(wf._usage_score({"count": 0}), 0.0)

    def test_used_recently_above_frequency_floor(self):
        score = wf._usage_score({"count": 1, "last_used": time.time()})
        self.assertGreater(score, 3.0)  # count*3 + positive recency bonus

    def test_frequency_dominates_over_recency(self):
        now = time.time()
        high_freq = wf._usage_score({"count": 10, "last_used": now - 60 * 86400})
        low_freq  = wf._usage_score({"count": 1,  "last_used": now})
        self.assertGreater(high_freq, low_freq)

    def test_recency_decays_over_time(self):
        now = time.time()
        score_recent = wf._usage_score({"count": 1, "last_used": now})
        score_old    = wf._usage_score({"count": 1, "last_used": now - 30 * 86400})
        self.assertGreater(score_recent, score_old)

    def test_sort_order_unused_last(self):
        now = time.time()
        statuses = [
            {"title": "Unused",  "text": "", "emoji": ""},
            {"title": "Popular", "text": "", "emoji": ""},
        ]
        usage = {"Popular": {"count": 5, "last_used": now}}
        sorted_s = sorted(statuses,
                          key=lambda s: (-wf._usage_score(usage.get(s["title"], {})),
                                        s["title"].lower()))
        self.assertEqual(sorted_s[0]["title"], "Popular")
        self.assertEqual(sorted_s[1]["title"], "Unused")

    def test_sort_order_unused_alphabetical(self):
        statuses = [
            {"title": "Zebra",  "text": "", "emoji": ""},
            {"title": "Apple",  "text": "", "emoji": ""},
            {"title": "Mango",  "text": "", "emoji": ""},
        ]
        sorted_s = sorted(statuses,
                          key=lambda s: (-wf._usage_score({}), s["title"].lower()))
        self.assertEqual([s["title"] for s in sorted_s], ["Apple", "Mango", "Zebra"])


# ── build_token_submenu ───────────────────────────────────────────────────────

class TestBuildTokenSubmenu(unittest.TestCase):

    def test_empty_input_is_invalid(self):
        items = wf.build_token_submenu("")
        self.assertEqual(len(items), 1)
        self.assertFalse(items[0]["valid"])
        self.assertIn("xoxp-", items[0]["title"])

    def test_valid_token_produces_save_item(self):
        items = wf.build_token_submenu("xoxp-123-abc-xyz-000")
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["valid"])
        self.assertIn("Save token", items[0]["title"])
        arg = json.loads(items[0]["arg"])
        self.assertEqual(arg["action"], "save_token")
        self.assertEqual(arg["token"], "xoxp-123-abc-xyz-000")

    def test_bare_xoxp_prefix_is_invalid(self):
        items = wf.build_token_submenu("xoxp-")
        self.assertFalse(items[0]["valid"])

    def test_unrecognized_string_is_invalid(self):
        items = wf.build_token_submenu("not-a-token")
        self.assertEqual(len(items), 1)
        self.assertFalse(items[0]["valid"])


# ── search_emoji ──────────────────────────────────────────────────────────────

class TestSearchEmoji(unittest.TestCase):

    def test_prefix_match_returns_results(self):
        results = wf.search_emoji("headphone")
        codes = [r[0] for r in results]
        self.assertIn("headphones", codes)

    def test_char_provided_for_standard_emoji(self):
        results = wf.search_emoji("headphone")
        for code, char in results:
            self.assertIsNotNone(char)
            self.assertGreater(len(char), 0)

    def test_no_match_returns_empty(self):
        results = wf.search_emoji("zzzznotarealemoji")
        self.assertEqual(results, [])

    def test_results_sorted_alphabetically(self):
        results = wf.search_emoji("fire")
        codes = [r[0] for r in results]
        prefix_codes   = [c for c in codes if c.startswith("fire")]
        substring_codes = [c for c in codes if not c.startswith("fire")]
        self.assertEqual(prefix_codes, sorted(prefix_codes))
        self.assertEqual(substring_codes, sorted(substring_codes))

    def test_substring_match_included(self):
        # 'ear' appears in 'bear' and 'heart', not just codes starting with 'ear'
        results = wf.search_emoji("ear")
        codes = [r[0] for r in results]
        self.assertTrue(any("ear" in c for c in codes))
        # At least one substring match (code that doesn't start with 'ear')
        self.assertTrue(any(not c.startswith("ear") and "ear" in c for c in codes))

    def test_prefix_before_substring(self):
        # Codes starting with 'heart' should appear before codes merely containing 'heart'
        results = wf.search_emoji("heart")
        codes = [r[0] for r in results]
        prefix_idxs   = [i for i, c in enumerate(codes) if c.startswith("heart")]
        substring_idxs = [i for i, c in enumerate(codes) if not c.startswith("heart")]
        if prefix_idxs and substring_idxs:
            self.assertLess(max(prefix_idxs), min(substring_idxs))

    def test_all_matches_returned(self):
        # No artificial limit — all prefix + substring matches come back
        results = wf.search_emoji("sun")
        codes = [r[0] for r in results]
        self.assertTrue(len(results) > 1)
        self.assertTrue(all("sun" in c for c in codes))

    def test_custom_emoji_yields_none_char(self):
        # Patch _load_custom_emoji to inject a fake custom emoji
        with mock.patch("common._load_custom_emoji", return_value={"zz_custom": "https://example.com/emoji.png"}):
            results = wf.search_emoji("zz_custom")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "zz_custom")
        self.assertIsNone(results[0][1])


# ── build_edit_submenu ────────────────────────────────────────────────────────

class TestBuildEditSubmenu(unittest.TestCase):

    STATUSES = [
        {"title": "Focusing",  "emoji": ":headphones:", "text": "Focusing",  "icon": "🎧"},
        {"title": "Deep work", "emoji": ":brain:",      "text": "Deep work", "icon": ":brain:"},
    ]

    def test_unknown_preset_returns_error_item(self):
        items = wf.build_edit_submenu("Ghost", "", self.STATUSES)
        self.assertEqual(len(items), 1)
        self.assertFalse(items[0].get("valid", True))

    def test_empty_query_returns_single_prompt_item(self):
        items = wf.build_edit_submenu("Focusing", "", self.STATUSES)
        self.assertEqual(len(items), 1)
        self.assertFalse(items[0].get("valid", True))

    def test_empty_query_autocomplete_contains_edit_infix(self):
        items = wf.build_edit_submenu("Focusing", "", self.STATUSES)
        ac = items[0].get("autocomplete", "")
        self.assertIn("» edit", ac)

    def test_empty_query_prefill_contains_current_values(self):
        items = wf.build_edit_submenu("Focusing", "", self.STATUSES)
        ac = items[0].get("autocomplete", "")
        self.assertIn("[Focusing]", ac)
        self.assertIn("🎧", ac)
        self.assertIn(":headphones:", ac)
        self.assertIn("Focusing", ac)

    def test_prefill_no_duplicate_code_when_icon_equals_emoji(self):
        items = wf.build_edit_submenu("Deep work", "", self.STATUSES)
        ac = items[0].get("autocomplete", "")
        self.assertNotIn(":brain: :brain:", ac)

    def test_prefill_includes_both_when_icon_differs_from_emoji(self):
        items = wf.build_edit_submenu("Focusing", "", self.STATUSES)
        ac = items[0].get("autocomplete", "")
        self.assertIn("🎧", ac)
        self.assertIn(":headphones:", ac)

    def test_valid_query_returns_save_item(self):
        items = wf.build_edit_submenu("Focusing", "[My Focus] :brain: Deep work", self.STATUSES)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].get("valid", False))

    def test_valid_query_arg_has_edit_preset_action(self):
        items = wf.build_edit_submenu("Focusing", "[My Focus] :brain: Deep work", self.STATUSES)
        arg = json.loads(items[0]["arg"])
        self.assertEqual(arg["action"], "edit_preset")

    def test_valid_query_arg_preserves_original_title_for_lookup(self):
        items = wf.build_edit_submenu("Focusing", "[My Focus] :brain: Deep work", self.STATUSES)
        arg = json.loads(items[0]["arg"])
        self.assertEqual(arg["title"], "Focusing")

    def test_valid_query_with_bracket_sets_new_title(self):
        items = wf.build_edit_submenu("Focusing", "[My Focus] :brain: Deep work", self.STATUSES)
        arg = json.loads(items[0]["arg"])
        self.assertEqual(arg["new_title"], "My Focus")

    def test_valid_query_without_bracket_has_no_new_title(self):
        items = wf.build_edit_submenu("Focusing", ":headphones: New text", self.STATUSES)
        arg = json.loads(items[0]["arg"])
        self.assertNotIn("new_title", arg)

    def test_valid_query_arg_has_correct_text_and_emoji(self):
        items = wf.build_edit_submenu("Focusing", "[My Focus] :brain: Deep work", self.STATUSES)
        arg = json.loads(items[0]["arg"])
        self.assertEqual(arg["text"], "Deep work")
        self.assertEqual(arg["emoji"], ":brain:")

    def test_save_item_title_shows_new_title_when_renamed(self):
        items = wf.build_edit_submenu("Focusing", "[My Focus] :brain: Deep work", self.STATUSES)
        self.assertIn("My Focus", items[0]["title"])

    def test_save_item_title_shows_original_title_when_not_renamed(self):
        items = wf.build_edit_submenu("Focusing", ":headphones: New text", self.STATUSES)
        self.assertIn("Focusing", items[0]["title"])


# ── format_expiry_countdown ───────────────────────────────────────────────────

class TestFormatExpiryCountdown(unittest.TestCase):

    def _fmt(self, expiration, now=FIXED_TIME):
        with mock.patch("common.time") as mt:
            mt.time.return_value = now
            return wf.format_expiry_countdown(expiration)

    def test_zero_returns_empty(self):
        self.assertEqual(self._fmt(0), "")

    def test_none_returns_empty(self):
        self.assertEqual(self._fmt(None), "")

    def test_past_timestamp_returns_clearing(self):
        self.assertEqual(self._fmt(FIXED_TIME - 1), "clearing…")

    def test_exact_zero_remaining_returns_clearing(self):
        self.assertEqual(self._fmt(FIXED_TIME), "clearing…")

    def test_seconds_under_60(self):
        self.assertEqual(self._fmt(FIXED_TIME + 42), "expires in 42s")

    def test_exactly_59_seconds(self):
        self.assertEqual(self._fmt(FIXED_TIME + 59), "expires in 59s")

    def test_exactly_60_seconds_is_minutes(self):
        self.assertEqual(self._fmt(FIXED_TIME + 60), "expires in 1m")

    def test_minutes(self):
        self.assertEqual(self._fmt(FIXED_TIME + 47 * 60), "expires in 47m")

    def test_exactly_one_hour(self):
        self.assertEqual(self._fmt(FIXED_TIME + 3600), "expires in 1h")

    def test_hours_and_minutes(self):
        self.assertEqual(self._fmt(FIXED_TIME + 2 * 3600 + 15 * 60), "expires in 2h 15m")

    def test_hours_exact_no_minutes_suffix(self):
        self.assertEqual(self._fmt(FIXED_TIME + 3 * 3600), "expires in 3h")


# ── current status cache ──────────────────────────────────────────────────────

class TestCurrentStatusCache(unittest.TestCase):

    def setUp(self):
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        self._orig = wf.CURRENT_STATUS_CACHE
        wf.CURRENT_STATUS_CACHE = self._tmp.name

    def tearDown(self):
        wf.CURRENT_STATUS_CACHE = self._orig
        os.unlink(self._tmp.name)

    def test_write_then_read_returns_data(self):
        with mock.patch("common.time") as mt:
            mt.time.return_value = FIXED_TIME
            wf.write_current_status_cache("Focusing", ":headphones:", 9999999)
            data = wf.load_current_status_cache()
        self.assertEqual(data["status_text"],       "Focusing")
        self.assertEqual(data["status_emoji"],      ":headphones:")
        self.assertEqual(data["status_expiration"], 9999999)

    def test_stale_cache_returns_none(self):
        with mock.patch("common.time") as mt:
            mt.time.return_value = FIXED_TIME
            wf.write_current_status_cache("Focusing", ":headphones:", 0)
        with mock.patch("common.time") as mt:
            mt.time.return_value = FIXED_TIME + wf._CURRENT_STATUS_TTL + 1
            result = wf.load_current_status_cache()
        self.assertIsNone(result)

    def test_fresh_cache_returns_data(self):
        with mock.patch("common.time") as mt:
            mt.time.return_value = FIXED_TIME
            wf.write_current_status_cache("Focusing", ":headphones:", 0)
        with mock.patch("common.time") as mt:
            mt.time.return_value = FIXED_TIME + wf._CURRENT_STATUS_TTL - 1
            result = wf.load_current_status_cache()
        self.assertIsNotNone(result)

    def test_missing_file_returns_none(self):
        os.unlink(self._tmp.name)
        open(self._tmp.name, "w").close()  # recreate empty
        wf.CURRENT_STATUS_CACHE = self._tmp.name + ".gone"
        self.assertIsNone(wf.load_current_status_cache())
        wf.CURRENT_STATUS_CACHE = self._tmp.name  # restore for tearDown

    def test_corrupt_file_returns_none(self):
        with open(self._tmp.name, "w") as f:
            f.write("not json{{{")
        self.assertIsNone(wf.load_current_status_cache())


# ── build_current_status_item ─────────────────────────────────────────────────

class TestBuildCurrentStatusItem(unittest.TestCase):

    def _build(self, cache_data, now=FIXED_TIME):
        with mock.patch("common.load_current_status_cache", return_value=cache_data), \
             mock.patch("common._fetch_current_status_async") as mock_fetch, \
             mock.patch("common.time") as mt:
            mt.time.return_value = now
            item = wf.build_current_status_item("xoxp-fake-token")
        return item, mock_fetch

    def test_cache_miss_returns_loading_item(self):
        item, _ = self._build(None)
        self.assertIn("Fetching", item["title"])
        self.assertFalse(item.get("valid", True))

    def test_cache_miss_fires_async_fetch(self):
        _, mock_fetch = self._build(None)
        mock_fetch.assert_called_once_with("xoxp-fake-token")

    def test_no_status_set_shows_no_status_item(self):
        item, _ = self._build({"status_text": "", "status_emoji": "", "status_expiration": 0})
        self.assertIn("No status", item["title"])
        self.assertFalse(item.get("valid", True))

    def test_no_status_has_no_cmd_mod(self):
        item, _ = self._build({"status_text": "", "status_emoji": "", "status_expiration": 0})
        self.assertNotIn("cmd", item.get("mods", {}))

    def test_active_status_shows_text_in_title(self):
        item, _ = self._build({"status_text": "Focusing", "status_emoji": ":headphones:", "status_expiration": 0})
        self.assertIn("Focusing", item["title"])

    def test_active_status_with_expiry_shows_countdown(self):
        expiry = FIXED_TIME + 47 * 60
        item, _ = self._build({"status_text": "Focusing", "status_emoji": ":headphones:", "status_expiration": expiry})
        self.assertIn("47m", item["subtitle"])

    def test_active_status_item_is_not_valid(self):
        item, _ = self._build({"status_text": "Focusing", "status_emoji": ":headphones:", "status_expiration": 0})
        self.assertFalse(item.get("valid", True))

    def test_active_status_cmd_mod_clears_status(self):
        item, _ = self._build({"status_text": "Focusing", "status_emoji": ":headphones:", "status_expiration": 0})
        cmd = item.get("mods", {}).get("cmd", {})
        self.assertTrue(cmd.get("valid", False))
        arg = json.loads(cmd["arg"])
        self.assertEqual(arg["text"], "")
        self.assertEqual(arg["emoji"], "")
        self.assertEqual(arg["expiry"], 0)

    def test_active_status_subtitle_includes_clear_hint(self):
        item, _ = self._build({"status_text": "Focusing", "status_emoji": ":headphones:", "status_expiration": 0})
        self.assertIn("⌘↩", item["subtitle"])

    def test_active_status_with_expiry_subtitle_includes_both_countdown_and_hint(self):
        expiry = FIXED_TIME + 47 * 60
        item, _ = self._build({"status_text": "Focusing", "status_emoji": ":headphones:", "status_expiration": expiry})
        self.assertIn("47m", item["subtitle"])
        self.assertIn("⌘↩", item["subtitle"])

    def test_no_token_does_not_fire_fetch(self):
        with mock.patch("common.load_current_status_cache", return_value=None), \
             mock.patch("common._fetch_current_status_async") as mock_fetch, \
             mock.patch("common.time") as mt:
            mt.time.return_value = FIXED_TIME
            wf.build_current_status_item("")
        mock_fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
