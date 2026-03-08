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


class TestCacheHelpers(unittest.TestCase):
    def test_find_and_load_latest_cache_json(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            self.assertIsNone(cache_manager.find_latest_cache_file(base, "holdings", "news", "AAPL"))
            self.assertEqual(
                cache_manager.load_latest_cache_json(base, "holdings", "news", "AAPL"),
                {},
            )

            d1 = base / "2026-03-07" / "holdings" / "news"
            d2 = base / "2026-03-08" / "holdings" / "news"
            d1.mkdir(parents=True, exist_ok=True)
            d2.mkdir(parents=True, exist_ok=True)
            (d1 / "AAPL.json").write_text('{"v":1}', encoding="utf-8")
            (d2 / "AAPL.json").write_text('{"v":2}', encoding="utf-8")
            latest = cache_manager.find_latest_cache_file(base, "holdings", "news", "AAPL")
            self.assertEqual(latest, d2 / "AAPL.json")
            self.assertEqual(
                cache_manager.load_latest_cache_json(base, "holdings", "news", "AAPL")["v"],
                2,
            )

    def test_load_latest_cache_json_invalid(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            d = base / "2026-03-08" / "holdings" / "news"
            d.mkdir(parents=True, exist_ok=True)
            (d / "AAPL.json").write_text("{bad-json", encoding="utf-8")
            self.assertEqual(
                cache_manager.load_latest_cache_json(base, "holdings", "news", "AAPL"),
                {},
            )

    def test_find_latest_news_analysis_file(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            self.assertIsNone(cache_manager.find_latest_news_analysis_file(base, "holdings", "AAPL"))
            d = base / "2026-03-08" / "holdings" / "news"
            d.mkdir(parents=True, exist_ok=True)
            p = d / "AAPL_analysis.json"
            p.write_text("{}", encoding="utf-8")
            self.assertEqual(
                cache_manager.find_latest_news_analysis_file(base, "holdings", "AAPL"),
                p,
            )


class TestCacheManager(unittest.TestCase):
    def test_should_refresh_fundamental(self):
        mgr = cache_manager.CacheManager(base_cache_dir="cache")
        real_date = datetime.date
        with patch("cache_manager.datetime.date") as mock_date:
            mock_date.today.return_value = real_date(2025, 1, 10)
            mock_date.fromisoformat.side_effect = real_date.fromisoformat
            self.assertTrue(mgr.should_refresh_fundamental(None))
            self.assertFalse(mgr.should_refresh_fundamental({}))
            self.assertFalse(mgr.should_refresh_fundamental({"next_earnings_date": "2025-01-11"}))
            self.assertTrue(mgr.should_refresh_fundamental({"next_earnings_date": "2025-01-10"}))
            self.assertTrue(mgr.should_refresh_fundamental({"next_earnings_date": "2025-01-09"}))
            self.assertFalse(mgr.should_refresh_fundamental({"next_earnings_date": 123}))

    def test_should_refresh_fundamental_requires_2_day_gap_after_expiry(self):
        mgr = cache_manager.CacheManager(base_cache_dir="cache")
        now = datetime.datetime.now()
        self.assertFalse(
            mgr.should_refresh_fundamental(
                {
                    "next_earnings_date": "2000-01-01",
                    "_cached_at": (now - datetime.timedelta(days=1)).isoformat(),
                }
            )
        )
        self.assertTrue(
            mgr.should_refresh_fundamental(
                {
                    "next_earnings_date": "2000-01-01",
                    "_cached_at": (now - datetime.timedelta(days=3)).isoformat(),
                }
            )
        )

    def test_set_get_is_valid_and_stats(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = cache_manager.CacheManager(
                config={"cache_ttl": {"news_hours": 30}},
                scope="holdings",
                base_cache_dir=Path(td),
            )
            mgr.set("news", "AAPL", {"articles": [{"title": "x"}]})
            self.assertTrue(mgr.is_valid("news", "AAPL"))
            got = mgr.get("news", "AAPL")
            self.assertIn("articles", got)
            self.assertEqual(mgr.stats["hits"], 1)

    def test_get_copy_logic_for_news_analysis(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            old_dir = base / "2026-03-07" / "holdings" / "news"
            old_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "_cached_at": (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat(),
                "articles": [{"title": "x"}],
            }
            (old_dir / "AAPL.json").write_text(json.dumps(payload), encoding="utf-8")
            (old_dir / "AAPL_analysis.json").write_text('{"k":1}', encoding="utf-8")

            mgr = cache_manager.CacheManager(scope="holdings", base_cache_dir=base)
            got = mgr.get("news", "AAPL")
            self.assertIn("articles", got)

            today = datetime.date.today().isoformat()
            copied_json = base / today / "holdings" / "news" / "AAPL.json"
            copied_analysis = base / today / "holdings" / "news" / "AAPL_analysis.json"
            self.assertTrue(copied_json.exists())
            self.assertTrue(copied_analysis.exists())

    def test_clear_has_fresh_and_clear_expired(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            mgr = cache_manager.CacheManager(scope="holdings", base_cache_dir=base)

            # Create fresh today news
            today = datetime.date.today().isoformat()
            d = base / today / "holdings" / "news"
            d.mkdir(parents=True, exist_ok=True)
            (d / "AAPL.json").write_text(
                json.dumps({"_cached_at": datetime.datetime.now().isoformat(), "x": 1}),
                encoding="utf-8",
            )
            self.assertTrue(mgr.has_fresh_today())

            # Create expired technical
            tdir = base / today / "holdings" / "technical"
            tdir.mkdir(parents=True, exist_ok=True)
            (tdir / "MSFT.json").write_text(
                json.dumps(
                    {
                        "_cached_at": (datetime.datetime.now() - datetime.timedelta(days=10)).isoformat(),
                        "x": 1,
                    }
                ),
                encoding="utf-8",
            )
            self.assertGreaterEqual(mgr.clear_expired(), 1)

            mgr.clear(category="news", symbol="AAPL")
            self.assertFalse((d / "AAPL.json").exists())

    def test_print_stats_and_get_ttl_and_earnings_season(self):
        mgr = cache_manager.CacheManager(
            config={"cache_ttl": {"fundamental_days": 1, "news_hours": 3, "company_info_days": 4}},
            base_cache_dir="cache",
        )
        self.assertEqual(mgr._get_ttl("news"), 3 * 3600)
        self.assertEqual(mgr._get_ttl("fundamental"), 1 * 24 * 3600)
        self.assertEqual(mgr._get_ttl("company_info"), 4 * 24 * 3600)
        with patch("builtins.print"):
            mgr.print_stats()
            mgr.stats["hits"] = 5
            mgr.stats["misses"] = 5
            mgr.print_stats()
        self.assertIn(mgr.is_earnings_season(), [True, False])


if __name__ == "__main__":
    unittest.main()
