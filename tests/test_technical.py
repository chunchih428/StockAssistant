import os
import sys
import unittest
from unittest.mock import MagicMock

import pandas as pd


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from market_data.technical import _safe_round, compute_technical_from_history, fetch_technical


class TestTechnicalHelpers(unittest.TestCase):
    def test_safe_round(self):
        self.assertEqual(_safe_round(1.2345, 2), 1.23)
        self.assertIsNone(_safe_round(None))
        self.assertIsNone(_safe_round(float("nan")))
        self.assertIsNone(_safe_round(object()))

    def test_compute_technical_from_history_full(self):
        close = pd.Series(range(1, 251), dtype="float64")
        vol = pd.Series([1000] * 250, dtype="float64")
        hist = pd.DataFrame({"Close": close, "Volume": vol})

        tech = compute_technical_from_history(hist)

        self.assertIn("ma50", tech)
        self.assertIn("ma200", tech)
        self.assertEqual(tech["ma50"], 225.5)
        self.assertEqual(tech["ma200"], 150.5)
        self.assertEqual(tech["high_52w"], 250.0)
        self.assertEqual(tech["low_52w"], 1.0)
        self.assertEqual(tech["current_price"], 250.0)
        self.assertEqual(tech["avg_vol_20d"], 1000)
        self.assertEqual(tech["current_vol"], 1000)
        self.assertAlmostEqual(tech["change_3mo_pct"], 30.89, places=2)

    def test_compute_technical_from_history_empty(self):
        hist = pd.DataFrame(columns=["Close", "Volume"])
        tech = compute_technical_from_history(hist)
        self.assertEqual(tech, {})


class TestFetchTechnical(unittest.TestCase):
    def test_fetch_technical_cache_hit(self):
        stock = MagicMock()
        cached = {"ma50": 100}
        tech, from_cache = fetch_technical("AAPL", stock, cached_tech=cached, cache_mgr=None)

        self.assertTrue(from_cache)
        self.assertEqual(tech["ma50"], 100)
        stock.history.assert_not_called()

    def test_fetch_technical_cache_miss_with_save(self):
        close = pd.Series(range(1, 251), dtype="float64")
        vol = pd.Series([1000] * 250, dtype="float64")
        hist = pd.DataFrame({"Close": close, "Volume": vol})

        stock = MagicMock()
        stock.history.return_value = hist
        cache_mgr = MagicMock()

        tech, from_cache = fetch_technical("AAPL", stock, cached_tech=None, cache_mgr=cache_mgr)

        self.assertFalse(from_cache)
        self.assertIn("ma50", tech)
        stock.history.assert_called_once_with(period="1y")
        cache_mgr.set.assert_called_once_with("technical", "AAPL", tech)


if __name__ == "__main__":
    unittest.main()

