import os
import sys
import unittest
from unittest.mock import MagicMock
import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from market_data import information


class TestInformation(unittest.TestCase):
    def test_parse_yf_news_new_format(self):
        item = {
            "content": {
                "title": "New iPhone",
                "pubDate": "2025-01-01T00:00:00Z",
                "canonicalUrl": {"url": "http://apple.com"},
                "provider": {"displayName": "Yahoo"},
            }
        }
        parsed = information.parse_yf_news(item)
        self.assertEqual(parsed["title"], "New iPhone")
        self.assertEqual(parsed["_source"], "yfinance")

    def test_parse_news_date_invalid(self):
        self.assertIsNone(information.parse_news_date("bad-date"))

    def test_fetch_news_no_key_returns_empty(self):
        fake_ticker = MagicMock()
        fake_ticker.news = []
        out = information.fetch_news(
            "AAPL",
            count=5,
            cache_mgr=None,
            company_name="Apple",
            env_get=lambda _k: None,
            ticker_factory=lambda _s: fake_ticker,
            print_fn=lambda *_args, **_kwargs: None,
        )
        self.assertEqual(out, [])

    def test_fetch_news(self):
        cache_instance = MagicMock()
        cache_instance.get.return_value = None
        now = datetime.datetime.now()
        dt_str = now.strftime("%Y-%m-%d %H:%M:%S")
        fake_ticker = MagicMock()
        fake_ticker.news = [
            {
                "title": "AAPL news from YF",
                "link": "link2",
                "providerPublishTime": int(now.timestamp()),
                "publisher": "Yahoo",
            }
        ]

        out = information.fetch_news(
            "AAPL",
            count=2,
            cache_mgr=cache_instance,
            env_get=lambda _k: "dummy_key",
            ticker_factory=lambda _s: fake_ticker,
            fetch_finnhub_news_fn=lambda _s, _k: [
                {
                    "title": "AAPL news from Finnhub",
                    "link": "link1",
                    "date": dt_str,
                    "publisher": "reuters",
                    "_source": "finnhub",
                }
            ],
            analyze_news_fn=lambda **_kwargs: None,
            print_fn=lambda *_args, **_kwargs: None,
        )

        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["symbol"], "AAPL")

    def test_fetch_news_cache_hit_short_circuit(self):
        cache = MagicMock()
        cache.get.return_value = {"articles": [{"title": "cached", "symbol": "AAPL"}]}
        out = information.fetch_news(
            "AAPL",
            count=5,
            cache_mgr=cache,
            analyze_news_fn=lambda **_kwargs: None,
            print_fn=lambda *_args, **_kwargs: None,
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["title"], "cached")
        cache.set.assert_not_called()

    def test_fetch_news_no_finnhub_key_and_yf_exception(self):
        cache = MagicMock()
        cache.get.return_value = None
        out = information.fetch_news(
            "AAPL",
            count=5,
            cache_mgr=cache,
            env_get=lambda _k: None,
            ticker_factory=lambda _s: (_ for _ in ()).throw(RuntimeError("yf error")),
            print_fn=lambda *_args, **_kwargs: None,
        )
        self.assertEqual(out, [])
        cache.set.assert_not_called()

    def test_fetch_news_finnhub_exception_still_returns_yf(self):
        cache = MagicMock()
        cache.get.return_value = None
        now = datetime.datetime.now()
        fake_ticker = MagicMock()
        fake_ticker.news = [
            {
                "title": "AAPL from YF",
                "link": "l2",
                "providerPublishTime": int(now.timestamp()),
                "publisher": "Yahoo",
            }
        ]
        out = information.fetch_news(
            "AAPL",
            count=5,
            cache_mgr=cache,
            env_get=lambda _k: "dummy_key",
            fetch_finnhub_news_fn=lambda _s, _k: (_ for _ in ()).throw(RuntimeError("fh error")),
            ticker_factory=lambda _s: fake_ticker,
            analyze_news_fn=lambda **_kwargs: None,
            print_fn=lambda *_args, **_kwargs: None,
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["symbol"], "AAPL")
        cache.set.assert_called_once()


if __name__ == "__main__":
    unittest.main()

