#!/usr/bin/env python3
"""
Tests for scheduling: when-spec parsing and the dispatcher due-logic in
workflow/common.py. Run with: python3 -m unittest discover tests
"""
import importlib.util
import os
import sys
import unittest
from datetime import datetime, timedelta

# Reuse a single shared "common" module object across test files. Loading a
# second instance would make mock.patch("common.time") in test_parsing target
# the wrong object and break time-frozen tests when the suite runs together.
if "common" in sys.modules:
    wf = sys.modules["common"]
else:
    _spec = importlib.util.spec_from_file_location(
        "common",
        os.path.join(os.path.dirname(__file__), "..", "workflow", "common.py"),
    )
    wf = importlib.util.module_from_spec(_spec)
    sys.modules["common"] = wf
    _spec.loader.exec_module(wf)

# A fixed reference "now": Monday, 2026-06-08, 10:00 local time.
NOW = datetime(2026, 6, 8, 10, 0, 0)


class TestParseTimeOfDay(unittest.TestCase):
    def test_am_pm(self):
        self.assertEqual(wf.parse_time_of_day("9am"),    (9, 0, "9:00 AM"))
        self.assertEqual(wf.parse_time_of_day("5pm"),    (17, 0, "5:00 PM"))
        self.assertEqual(wf.parse_time_of_day("12pm"),   (12, 0, "12:00 PM"))
        self.assertEqual(wf.parse_time_of_day("12am"),   (0, 0, "12:00 AM"))

    def test_with_minutes(self):
        self.assertEqual(wf.parse_time_of_day("9:30am"), (9, 30, "9:30 AM"))
        self.assertEqual(wf.parse_time_of_day("17:00"),  (17, 0, "5:00 PM"))
        self.assertEqual(wf.parse_time_of_day("9:00"),   (9, 0, "9:00 AM"))

    def test_named(self):
        self.assertEqual(wf.parse_time_of_day("noon"),     (12, 0, "12:00 PM"))
        self.assertEqual(wf.parse_time_of_day("midnight"), (0, 0, "12:00 AM"))

    def test_ambiguous_bare_integer_rejected(self):
        # No am/pm and no colon -> ambiguous -> rejected for schedules.
        self.assertIsNone(wf.parse_time_of_day("9"))
        self.assertIsNone(wf.parse_time_of_day("5"))

    def test_invalid(self):
        self.assertIsNone(wf.parse_time_of_day("foo"))
        self.assertIsNone(wf.parse_time_of_day("25:00"))


class TestParseScheduleWhen(unittest.TestCase):
    def _parse(self, text):
        return wf.parse_schedule_when(text, now=NOW)

    def test_recurring_weekdays(self):
        s = self._parse("weekdays 9am")
        self.assertEqual(s["kind"], "recurring")
        self.assertEqual(s["days"], [0, 1, 2, 3, 4])
        self.assertEqual((s["hour"], s["minute"]), (9, 0))

    def test_recurring_daily(self):
        s = self._parse("daily 12:30pm")
        self.assertEqual(s["days"], [0, 1, 2, 3, 4, 5, 6])
        self.assertEqual((s["hour"], s["minute"]), (12, 30))

    def test_recurring_weekends(self):
        s = self._parse("weekends 10am")
        self.assertEqual(s["days"], [5, 6])

    def test_recurring_day_list_comma(self):
        s = self._parse("mon,wed,fri 5pm")
        self.assertEqual(s["days"], [0, 2, 4])
        self.assertEqual(s["hour"], 17)

    def test_recurring_day_list_spaces(self):
        s = self._parse("tue thu 9:00")
        self.assertEqual(s["days"], [1, 3])

    def test_oneoff_in_duration(self):
        s = self._parse("in 2h")
        self.assertEqual(s["kind"], "one_off")
        self.assertEqual(s["timestamp"],
                         int((NOW + timedelta(hours=2)).timestamp()))

    def test_oneoff_tomorrow(self):
        s = self._parse("tomorrow 3pm")
        self.assertEqual(s["kind"], "one_off")
        self.assertEqual(s["timestamp"],
                         int(datetime(2026, 6, 9, 15, 0).timestamp()))

    def test_oneoff_today(self):
        s = self._parse("today 5pm")
        self.assertEqual(s["timestamp"],
                         int(datetime(2026, 6, 8, 17, 0).timestamp()))

    def test_oneoff_explicit_date(self):
        s = self._parse("2026-12-25 9am")
        self.assertEqual(s["kind"], "one_off")
        self.assertEqual(s["timestamp"],
                         int(datetime(2026, 12, 25, 9, 0).timestamp()))

    def test_oneoff_bare_time_next_occurrence(self):
        # 5pm is later than 10am today -> today at 5pm.
        s = wf.parse_schedule_when("5pm", now=NOW)
        self.assertEqual(s["kind"], "one_off")

    def test_invalid(self):
        self.assertIsNone(self._parse(""))
        self.assertIsNone(self._parse("weekdays"))      # no time
        self.assertIsNone(self._parse("sometime soon"))


class TestFmtDays(unittest.TestCase):
    def test_named_groups(self):
        self.assertEqual(wf._fmt_days([0, 1, 2, 3, 4, 5, 6]), "every day")
        self.assertEqual(wf._fmt_days([0, 1, 2, 3, 4]), "weekdays")
        self.assertEqual(wf._fmt_days([5, 6]), "weekends")

    def test_explicit(self):
        self.assertEqual(wf._fmt_days([0, 2, 4]), "Mon, Wed, Fri")


class TestEvaluateSchedule(unittest.TestCase):
    def _rec(self, **kw):
        base = {"id": "x", "kind": "recurring", "days": [0, 1, 2, 3, 4],
                "hour": 10, "minute": 0, "enabled": True}
        base.update(kw)
        return base

    def _one(self, ts, **kw):
        base = {"id": "y", "kind": "one_off", "timestamp": ts, "enabled": True}
        base.update(kw)
        return base

    def test_recurring_fires_within_grace(self):
        # NOW is Monday 10:00, schedule is weekdays 10:00 -> fire.
        action, key = wf.evaluate_schedule(self._rec(), NOW, set())
        self.assertEqual(action, "fire")
        self.assertEqual(key, "x@2026-06-08")

    def test_recurring_skips_already_fired(self):
        action, _ = wf.evaluate_schedule(self._rec(), NOW, {"x@2026-06-08"})
        self.assertEqual(action, "wait")

    def test_recurring_wrong_weekday(self):
        sat = datetime(2026, 6, 13, 10, 0)  # Saturday
        action, _ = wf.evaluate_schedule(self._rec(), sat, set())
        self.assertEqual(action, "wait")

    def test_recurring_stale_does_not_fire(self):
        late = datetime(2026, 6, 8, 10, 30)  # 30 min late, grace 300s
        action, _ = wf.evaluate_schedule(self._rec(), late, set())
        self.assertEqual(action, "wait")

    def test_recurring_disabled(self):
        action, _ = wf.evaluate_schedule(self._rec(enabled=False), NOW, set())
        self.assertEqual(action, "wait")

    def test_oneoff_fires_within_grace(self):
        ts = int(NOW.timestamp())
        action, key = wf.evaluate_schedule(self._one(ts), NOW, set())
        self.assertEqual(action, "fire")

    def test_oneoff_future_waits(self):
        ts = int((NOW + timedelta(minutes=10)).timestamp())
        action, _ = wf.evaluate_schedule(self._one(ts), NOW, set())
        self.assertEqual(action, "wait")

    def test_oneoff_missed_expires(self):
        ts = int((NOW - timedelta(hours=1)).timestamp())
        action, _ = wf.evaluate_schedule(self._one(ts), NOW, set())
        self.assertEqual(action, "expire")


if __name__ == "__main__":
    unittest.main()
