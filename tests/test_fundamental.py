import unittest
from unittest.mock import MagicMock, patch
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from market_data import fundamental_ai
from market_data import fundamental


class TestFundamental(unittest.TestCase):
    def test_translate_summary_with_gemini_v1(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'candidates': [{'content': {'parts': [{'text': 'translated summary'}]}}]
        }
        mock_post = MagicMock(return_value=mock_response)

        result = fundamental_ai.translate_summary_with_gemini_v1(
            'English Text',
            env_get=lambda _k: 'mock-key',
            requests_post=mock_post,
            print_fn=lambda *_args, **_kwargs: None,
        )
        self.assertEqual(result, 'translated summary')

    def test_translate_summary_with_gemini_v1_no_text(self):
        self.assertEqual(fundamental_ai.translate_summary_with_gemini_v1(''), '')

    def test_translate_summary_with_gemini_v1_no_key(self):
        self.assertEqual(
            fundamental_ai.translate_summary_with_gemini_v1('abc', env_get=lambda _k: None),
            'abc',
        )

    def test_translate_summary_with_gemini_v1_http_error_fallback(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = 'server error'
        mock_post = MagicMock(return_value=mock_response)
        text = 'Original English'
        self.assertEqual(
            fundamental_ai.translate_summary_with_gemini_v1(
                text,
                env_get=lambda _k: 'mock-key',
                requests_post=mock_post,
                print_fn=lambda *_args, **_kwargs: None,
            ),
            text,
        )

    def test_translate_summary_with_gemini_v1_exception_fallback(self):
        mock_post = MagicMock(side_effect=RuntimeError('timeout'))
        text = 'Original English'
        self.assertEqual(
            fundamental_ai.translate_summary_with_gemini_v1(
                text,
                env_get=lambda _k: 'mock-key',
                requests_post=mock_post,
                print_fn=lambda *_args, **_kwargs: None,
            ),
            text,
        )

    def test_extract_current_price_fallback(self):
        self.assertEqual(fundamental.extract_current_price({'currentPrice': 10}), 10)
        self.assertEqual(fundamental.extract_current_price({'regularMarketPrice': 20}), 20)
        self.assertEqual(fundamental.extract_current_price({'previousClose': 30}), 30)
        self.assertIsNone(fundamental.extract_current_price({}))

    def test_get_fundamental_data_from_cache(self):
        cached = {'company_name': 'Apple', 'marketCap': 1}
        stock = MagicMock()
        result, from_cache = fundamental.get_fundamental_data(
            symbol='AAPL',
            stock=stock,
            info={},
            current_price=150.0,
            cached_fund=cached,
            cache_mgr=None,
            translate_summary_fn=None,
        )
        self.assertTrue(from_cache)
        self.assertEqual(result['company_name'], 'Apple')
        self.assertEqual(result['current_price'], 150.0)

    def test_get_fundamental_data_new_build_and_cache(self):
        stock = MagicMock()
        stock.calendar = {'Earnings Date': ['2026-03-10']}
        cache_mgr = MagicMock()
        info = {
            'shortName': 'Apple',
            'longBusinessSummary': 'summary',
            'freeCashflow': 200,
            'totalRevenue': 1000,
            'totalDebt': 500,
            'totalCash': 120,
        }

        result, from_cache = fundamental.get_fundamental_data(
            symbol='AAPL',
            stock=stock,
            info=info,
            current_price=150.0,
            cached_fund=None,
            cache_mgr=cache_mgr,
            translate_summary_fn=lambda x: f"zh:{x}",
        )

        self.assertFalse(from_cache)
        self.assertEqual(result['company_name'], 'Apple')
        self.assertEqual(result['longBusinessSummary'], 'zh:summary')
        self.assertEqual(result['fcf_margin'], 20.0)
        self.assertEqual(result['net_debt'], 380)
        self.assertEqual(result['next_earnings_date'], '2026-03-10')
        cache_mgr.set.assert_called_once()

    def test_get_fundamental_data_calendar_error_is_ignored(self):
        stock = MagicMock()
        type(stock).calendar = property(lambda _self: (_ for _ in ()).throw(RuntimeError("boom")))
        result, from_cache = fundamental.get_fundamental_data(
            symbol='AAPL',
            stock=stock,
            info={'shortName': 'Apple'},
            current_price=150.0,
            cached_fund=None,
            cache_mgr=None,
            translate_summary_fn=None,
        )
        self.assertFalse(from_cache)
        self.assertEqual(result['company_name'], 'Apple')
        self.assertNotIn('next_earnings_date', result)

    @patch('market_data.fundamental.yf.Ticker')
    def test_fetch_fundamental(self, mock_ticker):
        stock = MagicMock()
        stock.info = {'currentPrice': 123, 'shortName': 'Apple'}
        stock.calendar = {}
        mock_ticker.return_value = stock
        cache_mgr = MagicMock()
        cache_mgr.get.return_value = None

        fundamental_data, price, from_cache = fundamental.fetch_fundamental(
            'AAPL',
            cache_mgr=cache_mgr,
            translate_summary_fn=None,
        )

        self.assertEqual(price, 123)
        self.assertFalse(from_cache)
        self.assertEqual(fundamental_data['company_name'], 'Apple')

    @patch('market_data.fundamental.yf.Ticker')
    def test_fetch_fundamental_cache_hit(self, mock_ticker):
        stock = MagicMock()
        stock.info = {'regularMarketPrice': 125}
        stock.calendar = {}
        mock_ticker.return_value = stock
        cache_mgr = MagicMock()
        cache_mgr.get.return_value = {'company_name': 'CachedCo'}

        fundamental_data, price, from_cache = fundamental.fetch_fundamental(
            'AAPL',
            cache_mgr=cache_mgr,
            translate_summary_fn=None,
        )

        self.assertEqual(price, 125)
        self.assertTrue(from_cache)
        self.assertEqual(fundamental_data['company_name'], 'CachedCo')


if __name__ == '__main__':
    unittest.main()

