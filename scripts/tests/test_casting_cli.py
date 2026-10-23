"""Casting entry behavior, independent classical examples, and source provenance."""
import importlib.util
import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, call
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import casting_cli as c
import liuyao_cli as n

COINS = ["000", "001", "011", "111", "010", "101"]
REQUEST = {"question": "我这次应聘能被录用吗？", "topic": "career_position", "subject_relation": "self"}

class Entry(unittest.TestCase):
    def test_question_only_waits_without_clock_generation_or_chart(self):
        with patch.object(c, "current_time", side_effect=AssertionError("clock read")), \
             patch.object(c, "random_coins", side_effect=AssertionError("cast generated")), \
             patch.object(n, "build_output", side_effect=AssertionError("chart built")):
            out = c.build_output(REQUEST)
        self.assertEqual(out["status"], "awaiting_casting_method")
        self.assertEqual(out["default_method"], "time_traditional")
        self.assertEqual(out["request"], REQUEST)
        self.assertNotIn("chart", out)
        self.assertEqual({x["id"] for x in out["methods"]}, {"time_traditional", "random", "time_seed"})

    def test_manual_wins_and_does_not_fill_missing_time(self):
        with patch.object(c, "current_time", side_effect=AssertionError("clock read")), \
             patch.object(c, "random_coins", side_effect=AssertionError("cast generated")):
            out = c.build_output({**REQUEST, "coins": COINS, "casting_method": "random"})
        self.assertEqual(out["casting"]["method"], "manual")
        self.assertEqual(out["input"]["coins"], COINS)
        self.assertEqual(out["calendar"]["status"], "missing")
        self.assertEqual(out["casting"]["time_source"], "missing")
        self.assertIsNone(out["casting"]["effective_cast_time"])

    def test_incomplete_manual_coins_are_not_replaced(self):
        for coins in (None, [], COINS[:5], [1] * 6, ["01"] * 6):
            with self.subTest(coins=coins), patch.object(c, "random_coins") as rng:
                with self.assertRaises(ValueError):
                    c.build_output({**REQUEST, "coins": coins, "casting_method": "random"})
                rng.assert_not_called()

    def test_bad_requests_fail_before_clock(self):
        for data in ({}, {"question": " "}, {**REQUEST, "casting_method": "default"},
                     {**REQUEST, "casting_method": []}, {**REQUEST, "moving_lines": [1]}):
            with self.subTest(data=data), patch.object(c, "current_time") as clock:
                with self.assertRaises(ValueError):
                    c.build_output(data)
                clock.assert_not_called()

    def test_cli_question_only(self):
        script = Path(c.__file__)
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(script)],
                                input=json.dumps(REQUEST), text=True, encoding="utf-8", capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "awaiting_casting_method")

    def test_classical_guanmei_example(self):
        values, details = c.traditional_values(5, 12, 17, 9)
        out = n.build_output({"coins": [c.ENCODING[x] for x in values]})
        self.assertEqual((details["upper_sum"], details["total"]), (34, 43))
        self.assertEqual(out["chart"]["primary"]["name"], "泽火革")
        self.assertEqual(out["chart"]["moving_positions"], [1])
        self.assertEqual(out["chart"]["changed"]["name"], "泽山咸")

    def test_classical_mudan_example_and_zero_remainders(self):
        values, _ = c.traditional_values(6, 3, 16, 4)
        chart = n.build_output({"coins": [c.ENCODING[x] for x in values]})["chart"]
        self.assertEqual((chart["primary"]["name"], chart["moving_positions"], chart["changed"]["name"]),
                         ("天风姤", [5], "火风鼎"))
        _, details = c.traditional_values(1, 1, 6, 4)
        self.assertEqual((details["upper_number"], details["lower_number"], details["moving_position"]), (8, 4, 6))

    def test_missing_dependency_fails_before_random_draw(self):
        with patch.object(n, "calendar_info", side_effect=RuntimeError("calendar unavailable")), \
             patch.object(c, "random_coins") as rng:
            with self.assertRaises(RuntimeError):
                c.build_output({**REQUEST, "casting_method": "random"}, now=datetime(2026, 3, 1, tzinfo=timezone.utc))
            rng.assert_not_called()

    def test_invalid_timestamp_fails_before_random_draw(self):
        for stamp in ("2026-03-01", "2026-03-01T12:30:00", "2026-02-30T12:30:00+08:00",
                      "2026-03-01T12:30:00+08:99"):
            with self.subTest(stamp=stamp), patch.object(c, "random_coins") as rng:
                with self.assertRaises(ValueError):
                    c.build_output({**REQUEST, "casting_method": "random", "cast_time": stamp})
                rng.assert_not_called()

@unittest.skipUnless(importlib.util.find_spec("lunar_python"), "lunar_python not installed")
class Generation(unittest.TestCase):
    def test_random_draws_eighteen_fair_bits_once_and_keeps_question(self):
        bits = [int(x) for group in COINS for x in group]
        instant = datetime(2026, 3, 1, 4, 5, 6, tzinfo=timezone.utc)
        with patch.object(c, "current_time", return_value=instant) as clock, \
             patch.object(c.secrets, "randbits", side_effect=bits) as rng:
            out = c.build_output({**REQUEST, "casting_method": "random"})
        clock.assert_called_once_with()
        self.assertEqual(rng.call_args_list, [call(1)] * 18)
        self.assertEqual(out["input"]["question"], REQUEST["question"])
        self.assertEqual(out["input"]["coins"], COINS)
        self.assertEqual(out["casting"]["raw_coins"], COINS)
        self.assertEqual(out["casting"]["effective_cast_time"], "2026-03-01T12:05:06+08:00")
        self.assertEqual(out["calendar"]["data"]["original_timestamp"], out["casting"]["generated_at"])
        self.assertEqual(out["chart"]["moving_positions"], [1, 4])

    def test_manual_historical_time_preserved(self):
        stamp = "2026-03-01T04:05:00Z"
        with patch.object(c, "current_time", side_effect=AssertionError("clock read")):
            out = c.build_output({**REQUEST, "coins": COINS, "cast_time": stamp})
        self.assertEqual(out["calendar"]["data"]["original_timestamp"], stamp)
        self.assertEqual(out["casting"]["effective_cast_time"], stamp)
        self.assertEqual(out["casting"]["time_source"], "user_provided")

    def test_seed_reproducible_for_same_instant_across_offsets(self):
        with patch.object(c, "random_coins", side_effect=AssertionError("random draw")):
            a = c.build_output({**REQUEST, "casting_method": "time_seed", "cast_time": "2026-03-01T04:05:00Z"})
            b = c.build_output({**REQUEST, "casting_method": "time_seed", "cast_time": "2026-03-01T12:05:00+08:00"})
        self.assertEqual(a["input"]["coins"], b["input"]["coins"])
        self.assertEqual(a["chart"], b["chart"])
        self.assertEqual(a["casting"]["seed_timestamp"], "2026-03-01T12:05:00+08:00")
        self.assertIsNone(a["casting"]["generated_at"])
        self.assertEqual(a["casting"]["time_source"], "user_provided")

    def test_traditional_lunar_new_year_not_gregorian_numbers(self):
        out = c.build_output({**REQUEST, "casting_method": "time_traditional",
                              "cast_time": "2026-02-17T00:01:00+08:00"})
        details = out["casting"]["parameters"]
        self.assertEqual((details["lunar_month"], details["lunar_day"], details["year_number"]), (1, 1, 7))
        self.assertEqual(out["chart"]["primary"]["name"], "天泽履")
        self.assertEqual(out["chart"]["moving_positions"], [4])
        self.assertEqual(out["chart"]["changed"]["name"], "风泽中孚")
        self.assertEqual(out["casting"]["coins_kind"], "synthetic_line_encoding_not_coin_tosses")

    def test_zi_boundary_changes_lunar_date_at_23(self):
        request = {**REQUEST, "casting_method": "time_traditional", "cast_time": "2026-02-16T23:30:00+08:00"}
        a = c.build_output({**request, "day_boundary": "midnight"})
        b = c.build_output({**request, "day_boundary": "zi_start"})
        self.assertEqual(a["casting"]["parameters"]["lunar_year"], 2025)
        self.assertEqual(b["casting"]["parameters"]["lunar_year"], 2026)
        self.assertEqual(b["chart"]["primary"]["name"], "天泽履")
        self.assertNotEqual(a["chart"]["primary"], b["chart"]["primary"])

    def test_leap_month_uses_repeated_month_number(self):
        out = c.build_output({**REQUEST, "casting_method": "time_traditional",
                              "cast_time": "2025-07-25T12:00:00+08:00"})
        details = out["casting"]["parameters"]
        self.assertTrue(details["leap_month"])
        self.assertEqual((details["lunar_month"], details["month_number"]), (-6, 6))

if __name__ == "__main__":
    unittest.main()
