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
        self.assertEqual(icon, "💬")
        self.assertEqual(emoji, ":school:")
        self.assertEqual(text, "Going to school")

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
