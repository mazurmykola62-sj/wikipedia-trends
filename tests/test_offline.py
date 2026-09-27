"""
Offline tests -- no network access required. Run with:
    cd tests && python3 -m pytest test_offline.py -v
or just:
    cd tests && python3 test_offline.py

These cover the parts of the pipeline that don't touch the network. Network-
dependent parts (fetch_pageviews.py's actual HTTP calls, resolve_topic.py's
Wikidata lookups) are NOT covered here -- this sandbox cannot reach
wikimedia.org / wikidata.org. See ../TESTING_NOTES.md for how to verify those
against the live API.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import common
from analyze_trend import robust_outliers, log_linear_trend, to_day_index, confidence_rating
from resolve_topic import requests_quote, strip_html


class TestCommon(unittest.TestCase):
    def test_parse_date_iso(self):
        self.assertEqual(common.parse_date("2023-09-01").isoformat(), "2023-09-01")

    def test_parse_date_compact(self):
        self.assertEqual(common.parse_date("20230901").isoformat(), "2023-09-01")

    def test_parse_date_invalid(self):
        with self.assertRaises(ValueError):
            common.parse_date("not-a-date")

    def test_clamp_before_data_start(self):
        from datetime import date
        self.assertEqual(common.clamp_to_data_availability(date(2010, 1, 1)), common.DATA_START)

    def test_to_api_date_format(self):
        from datetime import date
        self.assertEqual(common.to_api_date(date(2023, 9, 1)), "2023090100")


class TestResolveTopicHelpers(unittest.TestCase):
    def test_quote_handles_spaces_and_unicode(self):
        q = requests_quote("Post przerywany")
        self.assertNotIn(" ", q)

    def test_strip_html(self):
        self.assertEqual(strip_html("<span>Intermittent</span> fasting"), "Intermittent fasting")


class TestAnalyzeTrend(unittest.TestCase):
    def test_to_day_index(self):
        idx = to_day_index(["20230901", "20230902", "20230910"])
        self.assertEqual(idx, [0, 1, 9])

    def test_robust_outliers_flags_single_spike(self):
        values = [10.0] * 30
        values[15] = 500.0
        flagged = robust_outliers(values)
        self.assertIn(15, flagged)
        self.assertEqual(len(flagged), 1)

    def test_robust_outliers_ignores_stable_series(self):
        values = [10.0 + (i % 3) for i in range(30)]
        self.assertEqual(robust_outliers(values), [])

    def test_log_linear_trend_recovers_growth(self):
        # construct a perfectly exponential series with ~50%/year growth
        import math
        n = 365
        views = [100 * math.exp(math.log(1.5) * (i / 365)) for i in range(n)]
        day_idx = list(range(n))
        trend = log_linear_trend(day_idx, views)
        self.assertAlmostEqual(trend["annual_growth_rate"], 0.5, delta=0.02)
        self.assertGreater(trend["r_squared"], 0.99)

    def test_confidence_rating_low_for_sparse_noisy_data(self):
        conf = confidence_rating(total_views=200, span_days=30, r_squared=0.05, outlier_fraction=0.1, cv=2.0)
        self.assertEqual(conf["label"], "Low")
        self.assertGreater(len(conf["reasons"]), 0)

    def test_confidence_rating_high_for_clean_ample_data(self):
        conf = confidence_rating(total_views=200_000, span_days=730, r_squared=0.8, outlier_fraction=0.0, cv=0.3)
        self.assertEqual(conf["label"], "High")


if __name__ == "__main__":
    unittest.main(verbosity=2)
