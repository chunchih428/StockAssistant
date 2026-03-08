import datetime
import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from market_data import information


class TestInformationExtra(unittest.TestCase):
    def test_analyze_news_wrapper(self):
        called = {}

        def fake_impl(**kwargs):
            called.update(kwargs)

        with patch("market_data.information._analyze_news_with_gemini_impl", side_effect=fake_impl):
            information.analyze_news_with_gemini(symbol="AAPL", articles=[], cache_dir="cache")
        self.assertEqual(called["symbol"], "AAPL")

    def test_parse_yf_news_non_dict_and_missing(self):
        self.assertIsNone(information.parse_yf_news("x"))
        self.assertIsNone(information.parse_yf_news({"x": 1}))

    def test_parse_yf_news_old_format_bad_timestamp(self):
        out = information.parse_yf_news({"title": "t", "providerPublishTime": "bad", "link": "u", "publisher": "p"})
        self.assertEqual(out["date"], "")

    @patch("market_data.information.urllib.request.urlopen")
    def test_fetch_finnhub_news(self, mock_urlopen):
        data = [
            {"datetime": int(datetime.datetime.now().timestamp()), "headline": "h", "summary": "s", "url": "u", "source": "reuters"},
            {"datetime": "bad", "headline": "h2", "summary": "s2", "url": "u3", "source": "reuters"},
            {"datetime": 0, "headline": "", "summary": "", "url": "u2", "source": "x"},
        ]
        resp = MagicMock()
        resp.read.return_value = json.dumps(data).encode("utf-8")
        mock_urlopen.return_value = resp
        out = information.fetch_finnhub_news("AAPL", "k")
        self.assertEqual(len(out), 2)
        self.assertIn("_source", out[0])

    def test_parse_news_date_all_branches(self):
        self.assertIsNone(information.parse_news_date(""))
        self.assertIsNone(information.parse_news_date(object()))
        self.assertIsNotNone(information.parse_news_date(int(datetime.datetime.now().timestamp())))
        self.assertIsNone(information.parse_news_date(float("inf")))
        self.assertIsNotNone(information.parse_news_date("2026-03-08 12:00"))
        self.assertIsNotNone(information.parse_news_date("2026-03-08T12:00:00"))
        self.assertIsNotNone(information.parse_news_date("2026-03-08T12:00:00Z"))
        self.assertIsNotNone(information.parse_news_date("2026-03-08"))
        self.assertIsNone(information.parse_news_date("not-a-date"))

    def test_score_news_branches(self):
        now = datetime.datetime.now()
        arts = [
            {"title": "AAPL jumps", "publisher": "Reuters", "date": now.strftime("%Y-%m-%d %H:%M"), "_source": "finnhub"},
            {"title": "Apple news", "publisher": "Yahoo Finance", "date": "bad", "_source": "yfinance"},
            {"title": "No match", "publisher": "", "date": "", "_source": "x"},
        ]
        out = information.score_news(arts, "AAPL", "Apple Inc")
        self.assertGreaterEqual(len(out), 1)
        self.assertIn("_score", out[0])

    def test_score_news_publisher_else_and_tz_date(self):
        dt = "Tue, 08 Mar 2026 12:00:00 GMT"
        out = information.score_news(
            [{"title": "AAPL x", "publisher": "Some Blog", "date": dt, "_source": "other"}],
            "AAPL",
            "Apple",
        )
        self.assertEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main()
