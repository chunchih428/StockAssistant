import datetime
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cache_manager


class TestCacheManagerExtra(unittest.TestCase):
    def test_find_latest_cache_file_no_base(self):
        self.assertIsNone(cache_manager.find_latest_cache_file("not-exist-dir", "holdings", "news", "AAPL"))

    def test_find_latest_news_analysis_no_base(self):
        self.assertIsNone(cache_manager.find_latest_news_analysis_file("not-exist-dir", "holdings", "AAPL"))

    def test_is_valid_and_get_error_paths(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = cache_manager.CacheManager(scope="holdings", base_cache_dir=Path(td))
            self.assertFalse(mgr.is_valid("news", "AAPL"))
            self.assertIsNone(mgr.get("news", "AAPL"))

            d = Path(td) / datetime.date.today().isoformat() / "holdings" / "news"
            d.mkdir(parents=True, exist_ok=True)
            (d / "AAPL.json").write_text("bad-json", encoding="utf-8")
            self.assertFalse(mgr.is_valid("news", "AAPL"))
            self.assertIsNone(mgr.get("news", "AAPL"))

    def test_get_fundamental_refresh_miss(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = cache_manager.CacheManager(scope="holdings", base_cache_dir=Path(td))
            d = Path(td) / datetime.date.today().isoformat() / "holdings" / "fundamental"
            d.mkdir(parents=True, exist_ok=True)
            (d / "AAPL.json").write_text(
                json.dumps(
                    {
                        "next_earnings_date": "2000-01-01",
                        "_cached_at": (datetime.datetime.now() - datetime.timedelta(days=3)).isoformat(),
                    }
                ),
                encoding="utf-8",
            )
            self.assertIsNone(mgr.get("fundamental", "AAPL"))
            self.assertFalse(mgr.is_valid("fundamental", "AAPL"))

    def test_get_fundamental_not_refresh_within_2_days(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = cache_manager.CacheManager(scope="holdings", base_cache_dir=Path(td))
            d = Path(td) / datetime.date.today().isoformat() / "holdings" / "fundamental"
            d.mkdir(parents=True, exist_ok=True)
            (d / "AAPL.json").write_text(
                json.dumps(
                    {
                        "next_earnings_date": "2000-01-01",
                        "_cached_at": (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat(),
                        "company_name": "Apple",
                    }
                ),
                encoding="utf-8",
            )
            got = mgr.get("fundamental", "AAPL")
            self.assertIsNotNone(got)
            self.assertEqual(got.get("company_name"), "Apple")

    def test_get_expired_news_miss(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = cache_manager.CacheManager(scope="holdings", base_cache_dir=Path(td))
            d = Path(td) / datetime.date.today().isoformat() / "holdings" / "news"
            d.mkdir(parents=True, exist_ok=True)
            old = datetime.datetime.now() - datetime.timedelta(days=10)
            (d / "AAPL.json").write_text(json.dumps({"_cached_at": old.isoformat(), "articles": []}), encoding="utf-8")
            self.assertIsNone(mgr.get("news", "AAPL"))

    def test_clear_category_and_all(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = cache_manager.CacheManager(scope="holdings", base_cache_dir=Path(td))
            today = datetime.date.today().isoformat()
            for cat in ("fundamental", "technical", "news"):
                d = Path(td) / today / "holdings" / cat
                d.mkdir(parents=True, exist_ok=True)
                (d / "AAPL.json").write_text(json.dumps({"_cached_at": datetime.datetime.now().isoformat()}), encoding="utf-8")
            mgr.clear(category="news")
            mgr.clear()

    def test_clear_expired_misc_paths(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            mgr = cache_manager.CacheManager(scope="holdings", base_cache_dir=base)
            self.assertEqual(mgr.clear_expired(), 0)

            today = datetime.date.today().isoformat()
            n = base / today / "holdings" / "news"
            n.mkdir(parents=True, exist_ok=True)
            (n / "AAPL_analysis.json").write_text("{}", encoding="utf-8")
            (n / "BAD.json").write_text("{bad", encoding="utf-8")
            self.assertGreaterEqual(mgr.clear_expired(), 1)

    def test_has_fresh_today_false_and_clear_expired_fundamental(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            mgr = cache_manager.CacheManager(scope="holdings", base_cache_dir=base)
            self.assertFalse(mgr.has_fresh_today())

            day = "2026-03-08"
            fdir = base / day / "holdings" / "fundamental"
            fdir.mkdir(parents=True, exist_ok=True)
            (fdir / "AAPL.json").write_text(json.dumps({"next_earnings_date": "2000-01-01"}), encoding="utf-8")
            self.assertGreaterEqual(mgr.clear_expired(), 1)

    def test_clear_expired_base_not_exists(self):
        mgr = cache_manager.CacheManager(scope="holdings", base_cache_dir=Path("definitely_not_exists_cov_dir"))
        self.assertEqual(mgr.clear_expired(), 0)

    def test_print_stats_non_zero(self):
        mgr = cache_manager.CacheManager(base_cache_dir="cache")
        mgr.stats["hits"] = 1
        mgr.stats["misses"] = 1
        with patch("builtins.print") as p:
            mgr.print_stats()
            p.assert_called()


if __name__ == "__main__":
    unittest.main()
