import unittest

from unittest.mock import patch, mock_open, MagicMock

from pathlib import Path

import datetime

import json

import sys

import os



# Ensure the project directory is in the path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))



import stock_assistant
from market_data import analysis_ai
# ===== Merged from tests/test_claude_analysis.py =====

import unittest

from unittest.mock import patch, MagicMock, mock_open

import sys

import os

import json

import datetime
import runpy
import pandas as pd

from pathlib import Path



# Ensure the project directory is in the path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))



import stock_assistant



class TestClaudeAndHelpers(unittest.TestCase):



    def test_format_user_message(self):

        stock_info = {'symbol': 'AAPL', 'cost_basis': 140.0, 'shares': 100, 'category': 'Tech'}

        stock_data = {

            'fundamental': {

                'current_price': 150.0,

                'company_name': 'Apple Inc.',

                'sector': 'Technology',

                'industry': 'Electronics',

                'marketCap': 2.5e12,

                'enterpriseValue': 2.6e12,

                'trailingPE': 30,

                'forwardPE': 28,

                'dividendYield': 0.005

            },

            'technical': {

                'ma50': 145.0,

                'ma200': 135.0,

                'high_52w': 160.0,

                'low_52w': 120.0,

                'change_3mo_pct': 10.5,

                'avg_vol_20d': 1000000,

                'current_vol': 1200000

            }

        }

        news = [{'title': 'Test Apple News', 'link': 'link', 'publisher': 'Reuters', 'date': '2025-01-01'}]

        msg = analysis_ai.format_user_message(stock_info, stock_data, news)



        self.assertIn('AAPL', msg)

        self.assertIn('Apple Inc.', msg)

        self.assertIn('150.0', msg)

        self.assertIn('Test Apple News', msg)

        self.assertIn('Tech', msg)

        self.assertIn('近期消息', msg)



    @patch('market_data.analysis_ai.extract_summary')
    @patch('market_data.analysis_ai.anthropic.Anthropic')

    def test_analyze_with_claude(self, mock_anthropic, mock_extract_summary):

        mock_client = MagicMock()

        mock_anthropic.return_value = mock_client



        mock_response = MagicMock()

        # Mocking the nested structure for response.content[0].text

        mock_response.content = [MagicMock(text='AI analysis summary piece. ?遣霅?靽∪?摨阡? ?箸??5/5')]

        mock_response.usage.input_tokens = 100

        mock_response.usage.output_tokens = 50

        mock_client.messages.create.return_value = mock_response



        config = {'model': 'claude-3-sonnet', 'max_tokens': 100}
        mock_extract_summary.return_value = {
            'recommendation': 'add',
            'confidence': 'high',
            'scores': {'fundamental': 5},
        }



        stock_info = {'symbol': 'AAPL', 'cost_basis': 150.0, 'shares': 100, 'category': 'Tech'}
        result = stock_assistant.analyze_with_claude(stock_info, {'fundamental': {}}, [], 'system', config)

        self.assertEqual(result['recommendation'], 'add')

        self.assertIn('AI analysis', result['analysis'])

        self.assertEqual(result['input_tokens'], 100)



    @patch('market_data.analysis_ai.sys.exit')
    @patch('builtins.print')

    def test_api_error(self, mock_print, mock_exit):

        analysis_ai._api_error('Test Error')

        # Check that the error message was printed

        printed_calls = [call.args[0] for call in mock_print.call_args_list]

        self.assertTrue(any('Test Error' in str(msg) for msg in printed_calls))

        mock_exit.assert_called_with(1)



    def test_extract_summary(self):
        # Parser uses localized keywords; this test focuses on output schema stability.
        res = analysis_ai.extract_summary('Some analysis text with 3 / 5 score.')
        self.assertIn(res['recommendation'], ['add', 'reduce', 'hold', 'close', 'unknown'])
        self.assertIn(res['confidence'], ['high', 'medium', 'low'])
        self.assertIsInstance(res['scores'], dict)



    def test_calculate_allocation(self):

        results = [

            {

                'stock_info': {'symbol': 'AAPL', 'shares': 10, 'cost_basis': 150.0},

                'stock_data': {'fundamental': {'current_price': 160.0}}

            },

            {

                'stock_info': {'symbol': 'MSFT', 'shares': 5, 'cost_basis': 200.0},

                'stock_data': {'fundamental': {'current_price': 210.0}}

            }

        ]

        options = []

        cash = 1000.0



        alloc = stock_assistant.calculate_allocation(results, cash, options)

        self.assertEqual(alloc['cash'], 1000.0)
        # AAPL market val: 160 * 10 = 1600
        # MSFT market val: 210 * 5 = 1050
        # Total val: 1600 + 1050 + 1000 = 3650
        self.assertEqual(alloc['total_value'], 3650.0)

        # Total cost: (150*10) + (200*5) + 1000(cash stays same?)
        # Actually profit = (1600-1500) + (1050-1000) = 100 + 50 = 150
        self.assertEqual(alloc['total_pnl'], 150.0)


if __name__ == '__main__':

    unittest.main()


# ===== Merged from tests/test_config.py =====

import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import stock_assistant

# ===== Merged from tests/test_data_fetching.py =====

import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json
import datetime
import io
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import stock_assistant

class TestDataFetching(unittest.TestCase):

    def test_google_news_source_removed(self):
        # Current implementation no longer provides Google RSS helper.
        self.assertFalse(hasattr(stock_assistant, '_fetch_google_news'))

    @patch('stock_assistant.yf.Ticker')
    def test_fetch_stock_data_cache_hit_updates_live_price(self, mock_ticker):
        cache_mgr = MagicMock()
        cache_mgr.get.side_effect = [
            {'company_name': 'Apple'},
            {'ma50': 100},
        ]
        t = MagicMock()
        t.info = {'regularMarketPrice': 222.5}
        mock_ticker.return_value = t

        result = stock_assistant.fetch_stock_data('AAPL', cache_mgr=cache_mgr)
        self.assertEqual(result['fundamental']['current_price'], 222.5)
        self.assertEqual(result['technical']['ma50'], 100)

    @patch('stock_assistant.yf.Ticker', side_effect=RuntimeError('live fail'))
    def test_fetch_stock_data_cache_hit_live_price_exception(self, mock_ticker):
        cache_mgr = MagicMock()
        cache_mgr.get.side_effect = [{'company_name': 'Apple'}, {'ma50': 100}]
        result = stock_assistant.fetch_stock_data('AAPL', cache_mgr=cache_mgr)
        self.assertIn('fundamental', result)

    @patch('stock_assistant.yf.Ticker', side_effect=RuntimeError('yf down'))
    def test_fetch_stock_data_error_path(self, mock_ticker):
        cache_mgr = MagicMock()
        cache_mgr.get.side_effect = [None, None]
        result = stock_assistant.fetch_stock_data('AAPL', cache_mgr=cache_mgr)
        self.assertIn('error', result)
        self.assertEqual(result['fundamental'], {})
        self.assertEqual(result['technical'], {})

    @patch('stock_assistant.fetch_fundamental')
    @patch('stock_assistant.yf.Ticker')
    def test_fetch_stock_data_compute_technical_branch(self, mock_ticker, mock_fetch_fund):
        cache_mgr = MagicMock()
        cache_mgr.get.side_effect = [None, None]
        ticker = MagicMock()
        ticker.info = {'currentPrice': 150.0, 'shortName': 'Apple'}
        close = pd.Series(range(1, 251), dtype='float64')
        vol = pd.Series([1000] * 250, dtype='float64')
        ticker.history.return_value = pd.DataFrame({'Close': close, 'Volume': vol})
        mock_ticker.return_value = ticker
        mock_fetch_fund.return_value = ({'company_name': 'Apple', 'current_price': 150.0}, 150.0, False)

        result = stock_assistant.fetch_stock_data('AAPL', cache_mgr=cache_mgr)
        self.assertIn('ma50', result['technical'])
        self.assertIn('ma200', result['technical'])
        cache_mgr.set.assert_any_call('technical', 'AAPL', result['technical'])

    @patch('stock_assistant.fetch_fundamental', return_value=({'company_name': 'Apple', 'current_price': 150.0}, 150.0, True))
    @patch('stock_assistant.yf.Ticker')
    def test_fetch_stock_data_cached_fund_but_cached_tech(self, mock_ticker, mock_fetch_fund):
        cache_mgr = MagicMock()
        cache_mgr.get.side_effect = [{'company_name': 'Cached'}, {'ma50': 10}]
        t = MagicMock()
        t.info = {'currentPrice': 150.0}
        mock_ticker.return_value = t
        res = stock_assistant.fetch_stock_data('AAPL', cache_mgr=cache_mgr)
        self.assertEqual(res['fundamental']['current_price'], 150.0)

    @patch('stock_assistant.fetch_fundamental', return_value=({'company_name': 'Apple', 'current_price': 150.0}, 150.0, True))
    @patch('stock_assistant.yf.Ticker')
    def test_fetch_stock_data_fund_from_cache_branch(self, mock_ticker, mock_fetch_fund):
        cache_mgr = MagicMock()
        cache_mgr.get.side_effect = [{'company_name': 'Cached'}, None]
        t = MagicMock()
        t.info = {'currentPrice': 150.0}
        close = pd.Series(range(1, 80), dtype='float64')
        vol = pd.Series([1000] * 79, dtype='float64')
        t.history.return_value = pd.DataFrame({'Close': close, 'Volume': vol})
        mock_ticker.return_value = t
        res = stock_assistant.fetch_stock_data('AAPL', cache_mgr=cache_mgr)
        self.assertEqual(res['fundamental']['company_name'], 'Apple')

    @patch('stock_assistant.fetch_fundamental', return_value=({'company_name': 'Apple', 'current_price': 150.0}, 150.0, False))
    @patch('stock_assistant.yf.Ticker')
    def test_fetch_stock_data_cached_tech_no_cached_fund(self, mock_ticker, mock_fetch_fund):
        cache_mgr = MagicMock()
        cache_mgr.get.side_effect = [None, {'ma50': 10}]
        t = MagicMock()
        t.info = {'currentPrice': 150.0, 'longBusinessSummary': 'abc'}
        mock_ticker.return_value = t
        res = stock_assistant.fetch_stock_data('AAPL', cache_mgr=cache_mgr)
        self.assertEqual(res['technical']['ma50'], 10)


class TestImportGuard(unittest.TestCase):
    def test_missing_dependency_exit(self):
        orig_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == 'anthropic':
                raise ImportError("missing anthropic")
            return orig_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=fake_import), \
             patch('sys.exit', side_effect=SystemExit), \
             patch('builtins.print'):
            with self.assertRaises(SystemExit):
                runpy.run_path(str(Path(__file__).resolve().parents[1] / 'stock_assistant.py'))


class TestClaudeExceptions(unittest.TestCase):
    def test_analyze_with_claude_exception_paths(self):
        stock_info = {'symbol': 'AAPL', 'cost_basis': 1, 'shares': 1}
        config = {'model': 'm', 'max_tokens': 1}

        class AuthE(Exception): pass
        class PermE(Exception): pass
        class NotFoundE(Exception): pass
        class RateE(Exception): pass
        class ConnE(Exception): pass
        class BadReqE(Exception):
            def __init__(self, message): self.message = message
        class StatusE(Exception):
            def __init__(self, status_code, message):
                self.status_code = status_code
                self.message = message

        with patch.object(analysis_ai.anthropic, 'AuthenticationError', AuthE), \
             patch.object(analysis_ai.anthropic, 'PermissionDeniedError', PermE), \
             patch.object(analysis_ai.anthropic, 'NotFoundError', NotFoundE), \
             patch.object(analysis_ai.anthropic, 'RateLimitError', RateE), \
             patch.object(analysis_ai.anthropic, 'BadRequestError', BadReqE), \
             patch.object(analysis_ai.anthropic, 'APIConnectionError', ConnE), \
             patch.object(analysis_ai.anthropic, 'APIStatusError', StatusE):
            cases = [AuthE(), PermE(), NotFoundE(), RateE(), BadReqE('bad'), ConnE(), StatusE(500, 'x')]
            for exc in cases:
                with self.subTest(exc=type(exc).__name__):
                    client = MagicMock()
                    client.messages.create.side_effect = exc
                    with patch('market_data.analysis_ai.anthropic.Anthropic', return_value=client), \
                         patch('market_data.analysis_ai._api_error') as mock_api_error:
                        stock_assistant.analyze_with_claude(stock_info, {'fundamental': {}}, [], 'sys', config)
                        mock_api_error.assert_called_once()


class TestSummaryParser(unittest.TestCase):
    def test_extract_summary_all_recommendations(self):
        self.assertEqual(analysis_ai.extract_summary('建議加倉，信心高')['recommendation'], 'add')
        self.assertEqual(analysis_ai.extract_summary('建議平倉')['recommendation'], 'close')
        self.assertEqual(analysis_ai.extract_summary('建議減碼，信心低')['recommendation'], 'reduce')
        self.assertEqual(analysis_ai.extract_summary('建議維持')['recommendation'], 'hold')
        s = analysis_ai.extract_summary('基本面 5/5 技術面 4／5 風險 3/5')
        self.assertEqual(s['scores']['fundamental'], 5)
        self.assertEqual(s['scores']['technical'], 4)
        self.assertEqual(s['scores']['risk'], 3)

    def test_format_user_message_numeric_format_branches(self):
        msg = analysis_ai.format_user_message(
            {'symbol': 'AAPL', 'cost_basis': 100.0, 'shares': 1},
            {
                'fundamental': {
                    'company_name': 'Apple',
                    'current_price': 90.0,
                    'marketCap': 2e9,      # B branch
                    'enterpriseValue': 3e6, # M branch
                },
                'technical': {
                    'avg_vol_20d': object(),  # triggers format fallback str(v)
                },
            },
            [],
        )
        self.assertIn('$2.00B', msg)
        self.assertIn('$3.00M', msg)
        self.assertIn('$90', msg)

    def test_format_user_message_small_number_branch(self):
        msg = analysis_ai.format_user_message(
            {'symbol': 'AAPL', 'cost_basis': 1.0, 'shares': 1},
            {'fundamental': {'company_name': 'Apple', 'current_price': 1.0, 'marketCap': 500}, 'technical': {}},
            [],
        )
        self.assertIn('$500', msg)


class TestNewsParserEdges(unittest.TestCase):
    pass


if __name__ == '__main__':
    unittest.main()


# ===== Merged from tests/test_main.py =====

import unittest

from unittest.mock import patch, MagicMock, mock_open

import sys

import os

import json

import datetime

from pathlib import Path



sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))



import stock_assistant



class TestMain(unittest.TestCase):



    def setUp(self):
        # Reset any state if necessary
        pass

    @patch('stock_assistant.fetch_news', return_value=[])
    @patch('stock_assistant.fetch_stock_data')
    @patch('stock_assistant.Path.exists', return_value=True)
    @patch('stock_assistant.Path.read_text', return_value='{"holdings": {"AAPL": ["MSFT"]}, "competitors": {}}')
    def test_fetch_competitor_data_company_name_add_when_missing(self, mock_read, mock_exists, mock_stock, mock_news):
        company_names = {}
        mock_stock.return_value = {'symbol': 'MSFT', 'fundamental': {'company_name': 'Microsoft'}, 'technical': {}}
        res = stock_assistant.fetch_competitor_data([{'symbol': 'AAPL'}], MagicMock(), company_names)
        self.assertEqual(len(res), 1)
        self.assertEqual(company_names['MSFT'], 'Microsoft')



    @patch('stock_assistant.StockPrerun')
    @patch('stock_assistant.webbrowser.open')
    def test_main_open(self, mock_browser, mock_prerun_class):
        mock_prerun = mock_prerun_class.return_value
        mock_prerun.check_setup.return_value = True
        mock_prerun.load_config.return_value = {}

        with patch.object(stock_assistant, 'HTML_FILE', MagicMock(spec=Path)) as mock_html:

            mock_html.exists.return_value = True

            mock_html.absolute.return_value = 'test_path'

            with patch.object(sys, 'argv', ['stock_assistant.py', '--open']):

                stock_assistant.main()

        mock_browser.assert_called_once()



    @patch('stock_assistant.StockPrerun')
    @patch('stock_assistant.fetch_stock_data')
    @patch('stock_assistant.fetch_news')
    @patch('stock_assistant.Path.exists', return_value=True)
    @patch('stock_assistant.Path.read_text', return_value='{"holdings": {"AAPL": ["MSFT"]}, "competitors": {}}')
    def test_fetch_competitor_data(self, mock_read, mock_exists, mock_news, mock_stock, mock_prerun_class):
        mock_prerun = mock_prerun_class.return_value
        mock_prerun.check_setup.return_value = True
        mock_prerun.load_config.return_value = {}

        company_names = {'MSFT': 'Microsoft'}

        mock_stock.return_value = {'symbol': 'MSFT', 'fundamental': {'company_name': 'Microsoft'}, 'technical': {}}

        mock_news.return_value = []



        cache_mgr = MagicMock()

        res = stock_assistant.fetch_competitor_data([{'symbol': 'AAPL'}], cache_mgr, company_names)

        self.assertEqual(len(res), 1)

        self.assertEqual(res[0]['stock_info']['symbol'], 'MSFT')

    @patch('stock_assistant.count_recommendations', return_value={'add': 1, 'reduce': 0, 'close': 0})
    @patch('stock_assistant.generate_html', return_value='<html>ok</html>')
    @patch('stock_assistant.calculate_allocation')
    @patch('stock_assistant.fetch_competitor_data', return_value=[])
    @patch('stock_assistant.fetch_news', return_value=[])
    @patch('stock_assistant.fetch_stock_data')
    @patch('stock_assistant.time.sleep')
    @patch('stock_assistant.StockPrerun')
    def test_main_full_flow_no_api_key(
        self,
        mock_prerun_class,
        mock_sleep,
        mock_fetch_stock_data,
        mock_fetch_news,
        mock_fetch_competitor_data,
        mock_calc_alloc,
        mock_generate_html,
        mock_count_recs,
    ):
        mock_prerun = mock_prerun_class.return_value
        mock_prerun.check_setup.return_value = False
        mock_prerun.load_config.return_value = {'news_count': 2, 'skip_tickers': [], 'only_tickers': []}
        mock_prerun.load_portfolio.return_value = (
            [{'symbol': 'AAPL', 'shares': 10, 'cost_basis': 100.0, 'category': 'Tech'}],
            [],
            1000.0,
        )
        mock_prerun.load_company_names.return_value = {'AAPL': 'Apple'}

        mock_fetch_stock_data.return_value = {
            'symbol': 'AAPL',
            'fundamental': {'company_name': 'Apple', 'current_price': 110.0},
            'technical': {'ma50': 100.0, 'ma200': 90.0},
        }
        mock_calc_alloc.return_value = {
            'total_value': 2100.0,
            'total_pnl': 100.0,
            'cash': 1000.0,
            'cash_pct': 47.6,
            'positions': [],
            'options_value': 0.0,
            'options_pct': 0.0,
        }

        with patch.object(stock_assistant, 'RESULTS_FILE', MagicMock(spec=Path)) as mock_results_file, \
             patch.object(stock_assistant, 'HTML_FILE', MagicMock(spec=Path)) as mock_html_file, \
             patch.object(sys, 'argv', ['stock_assistant.py']):
            mock_html_file.absolute.return_value = Path('index.html')
            stock_assistant.main()

        mock_prerun.process_cache.assert_called_once()
        mock_fetch_stock_data.assert_called_once()
        mock_fetch_news.assert_called_once()
        mock_calc_alloc.assert_called_once()
        mock_generate_html.assert_called_once()
        mock_results_file.write_text.assert_called_once()
        mock_html_file.write_text.assert_called_once()
        mock_prerun.save_company_names.assert_called_once()

    @patch('stock_assistant.StockPrerun')
    def test_main_no_stocks_returns_early(self, mock_prerun_class):
        mock_prerun = mock_prerun_class.return_value
        mock_prerun.check_setup.return_value = False
        mock_prerun.load_config.return_value = {'skip_tickers': [], 'only_tickers': []}
        mock_prerun.load_portfolio.return_value = ([], [], 0.0)
        mock_prerun.load_company_names.return_value = {}

        with patch.object(sys, 'argv', ['stock_assistant.py']), \
             patch('stock_assistant.fetch_stock_data') as mock_fetch_stock_data:
            stock_assistant.main()

        mock_fetch_stock_data.assert_not_called()

    @patch('stock_assistant.StockPrerun')
    def test_main_open_when_html_missing(self, mock_prerun_class):
        with patch.object(stock_assistant, 'HTML_FILE', MagicMock(spec=Path)) as mock_html, \
             patch.object(sys, 'argv', ['stock_assistant.py', '--open']), \
             patch('stock_assistant.webbrowser.open') as mock_open:
            mock_html.exists.return_value = False
            stock_assistant.main()
        mock_open.assert_not_called()

    @patch('stock_assistant.count_recommendations', return_value={'add': 0, 'reduce': 0, 'close': 0})
    @patch('stock_assistant.generate_html', return_value='<html>ok</html>')
    @patch('stock_assistant.calculate_allocation', return_value={'total_value': 1, 'total_pnl': 0, 'cash': 0, 'cash_pct': 0, 'positions': [], 'options_value': 0, 'options_pct': 0})
    @patch('stock_assistant.fetch_competitor_data', return_value=[])
    @patch('stock_assistant.fetch_news', return_value=[])
    @patch('stock_assistant.fetch_stock_data', return_value={'fundamental': {'current_price': 1}, 'technical': {'ma50': 1, 'ma200': 1}})
    @patch('stock_assistant.time.sleep')
    @patch('stock_assistant.StockPrerun')
    def test_main_skip_competitor_bootstrap_flag(
        self, mock_prerun_class, mock_sleep, *_mocks
    ):
        mock_prerun = mock_prerun_class.return_value
        mock_prerun.check_setup.return_value = False
        mock_prerun.load_config.return_value = {'skip_tickers': [], 'only_tickers': []}
        mock_prerun.load_portfolio.return_value = ([{'symbol': 'AAPL', 'shares': 1, 'cost_basis': 1}], [], 0.0)
        mock_prerun.load_company_names.return_value = {}

        with patch.object(stock_assistant, 'RESULTS_FILE', MagicMock(spec=Path)), \
             patch.object(stock_assistant, 'HTML_FILE', MagicMock(spec=Path)) as mock_html_file, \
             patch.object(sys, 'argv', ['stock_assistant.py', '--skip-competitor-bootstrap']):
            mock_html_file.absolute.return_value = Path('index.html')
            stock_assistant.main()

        mock_prerun.auto_populate_competitors.assert_not_called()
        mock_prerun.ensure_competitor_names.assert_not_called()

    @patch('stock_assistant.count_recommendations', return_value={'add': 0, 'reduce': 0, 'close': 0})
    @patch('stock_assistant.generate_html', return_value='<html>ok</html>')
    @patch('stock_assistant.calculate_allocation', return_value={'total_value': 1, 'total_pnl': 0, 'cash': 0, 'cash_pct': 0, 'positions': [], 'options_value': 0, 'options_pct': 0})
    @patch('stock_assistant.fetch_competitor_data', return_value=[])
    @patch('stock_assistant.fetch_news', return_value=[])
    @patch('stock_assistant.fetch_stock_data', return_value={'fundamental': {'current_price': 1}, 'technical': {'ma50': 1, 'ma200': 1}})
    @patch('stock_assistant.time.sleep')
    @patch('stock_assistant.StockPrerun')
    def test_main_skip_competitor_bootstrap_short_flag(
        self, mock_prerun_class, mock_sleep, *_mocks
    ):
        mock_prerun = mock_prerun_class.return_value
        mock_prerun.check_setup.return_value = False
        mock_prerun.load_config.return_value = {'skip_tickers': [], 'only_tickers': []}
        mock_prerun.load_portfolio.return_value = ([{'symbol': 'AAPL', 'shares': 1, 'cost_basis': 1}], [], 0.0)
        mock_prerun.load_company_names.return_value = {}

        with patch.object(stock_assistant, 'RESULTS_FILE', MagicMock(spec=Path)), \
             patch.object(stock_assistant, 'HTML_FILE', MagicMock(spec=Path)) as mock_html_file, \
             patch.object(sys, 'argv', ['stock_assistant.py', '-sc']):
            mock_html_file.absolute.return_value = Path('index.html')
            stock_assistant.main()

        mock_prerun.auto_populate_competitors.assert_not_called()
        mock_prerun.ensure_competitor_names.assert_not_called()

    @patch('stock_assistant.count_recommendations', return_value={'add': 0, 'reduce': 1, 'close': 0})
    @patch('stock_assistant.generate_html', return_value='<html>ok</html>')
    @patch('stock_assistant.calculate_allocation')
    @patch('stock_assistant.fetch_competitor_data')
    @patch('stock_assistant.analyze_with_claude')
    @patch('stock_assistant.fetch_news', return_value=[])
    @patch('stock_assistant.fetch_stock_data')
    @patch('stock_assistant.time.sleep')
    @patch('stock_assistant.StockPrerun')
    def test_main_cli_only_skip_and_api_flow(
        self,
        mock_prerun_class,
        mock_sleep,
        mock_fetch_stock_data,
        mock_fetch_news,
        mock_analyze,
        mock_fetch_comp,
        mock_calc,
        mock_gen_html,
        mock_count,
    ):
        mock_prerun = mock_prerun_class.return_value
        mock_prerun.check_setup.return_value = True
        mock_prerun.load_config.return_value = {
            'news_count': 2,
            'only_tickers': ['AAPL', 'MSFT'],
            'skip_tickers': ['MSFT'],
            'model': 'claude-sonnet-4-6',
        }
        mock_prerun.load_portfolio.return_value = (
            [
                {'symbol': 'AAPL', 'shares': 1, 'cost_basis': 100.0, 'category': 'Tech'},
                {'symbol': 'MSFT', 'shares': 1, 'cost_basis': 100.0, 'category': 'Tech'},
            ],
            [],
            0.0,
        )
        mock_prerun.load_company_names.return_value = {}
        mock_fetch_stock_data.return_value = {
            'symbol': 'AAPL',
            'fundamental': {'company_name': 'Apple', 'current_price': 110.0, 'returnOnEquity': 0.2},
            'technical': {'ma50': 100.0, 'ma200': 90.0},
        }
        mock_analyze.return_value = {'recommendation': 'reduce', 'scores': {}, 'analysis': 'x'}
        mock_fetch_comp.return_value = [{
            'stock_info': {'symbol': 'NVDA', 'shares': 0, 'cost_basis': 0, 'category': '競品參考'},
            'stock_data': {'fundamental': {}, 'technical': {}},
            'news': [],
            'analysis_result': {'recommendation': 'unknown', 'scores': {}, 'analysis': ''},
        }]
        mock_calc.return_value = {
            'total_value': 110.0,
            'total_pnl': 10.0,
            'cash': 0.0,
            'cash_pct': 0.0,
            'positions': [],
            'options_value': 0.0,
            'options_pct': 0.0,
        }

        with patch.object(stock_assistant, 'RESULTS_FILE', MagicMock(spec=Path)) as mock_results_file, \
             patch.object(stock_assistant, 'HTML_FILE', MagicMock(spec=Path)) as mock_html_file, \
             patch.object(sys, 'argv', ['stock_assistant.py', 'AAPL', 'TSLA']):
            mock_html_file.absolute.return_value = Path('index.html')
            stock_assistant.main()

        mock_analyze.assert_called_once()
        mock_fetch_comp.assert_called_once()
        mock_prerun.save_company_names.assert_called()
        mock_results_file.write_text.assert_called_once()
        mock_html_file.write_text.assert_called_once()

    @patch('stock_assistant.count_recommendations', return_value={'add': 0, 'reduce': 0, 'close': 0})
    @patch('stock_assistant.generate_html', return_value='<html>ok</html>')
    @patch('stock_assistant.calculate_allocation', return_value={'total_value': 1, 'total_pnl': 0, 'cash': 0, 'cash_pct': 0, 'positions': [], 'options_value': 0, 'options_pct': 0})
    @patch('stock_assistant.fetch_competitor_data', return_value=[])
    @patch('stock_assistant.fetch_news', return_value=[])
    @patch('stock_assistant.fetch_stock_data')
    @patch('stock_assistant.time.sleep')
    @patch('stock_assistant.StockPrerun')
    def test_main_only_config_branch_and_skip_ai_on_error(
        self, mock_prerun_class, mock_sleep, mock_fetch_data, mock_fetch_news,
        mock_fetch_comp, mock_calc, mock_html, mock_count
    ):
        mock_prerun = mock_prerun_class.return_value
        mock_prerun.check_setup.return_value = True
        mock_prerun.load_config.return_value = {'only_tickers': ['MSFT'], 'skip_tickers': [], 'news_count': 1}
        mock_prerun.load_portfolio.return_value = (
            [
                {'symbol': 'AAPL', 'shares': 1, 'cost_basis': 100, 'category': 'Tech'},
                {'symbol': 'MSFT', 'shares': 1, 'cost_basis': 100, 'category': 'Tech'},
            ], [], 0.0
        )
        mock_prerun.load_company_names.return_value = {}
        mock_fetch_data.return_value = {'symbol': 'MSFT', 'error': 'boom', 'fundamental': {'current_price': 90}, 'technical': {'ma50': 100}}

        with patch.object(stock_assistant, 'RESULTS_FILE', MagicMock(spec=Path)), \
             patch.object(stock_assistant, 'HTML_FILE', MagicMock(spec=Path)) as mock_html_file, \
             patch.object(sys, 'argv', ['stock_assistant.py']):
            mock_html_file.absolute.return_value = Path('index.html')
            stock_assistant.main()

        mock_sleep.assert_not_called()

    @patch('stock_assistant.count_recommendations', return_value={'add': 0, 'reduce': 0, 'close': 0})
    @patch('stock_assistant.generate_html', return_value='<html>ok</html>')
    @patch('stock_assistant.calculate_allocation', return_value={'total_value': 1, 'total_pnl': 0, 'cash': 0, 'cash_pct': 0, 'positions': [], 'options_value': 0, 'options_pct': 0})
    @patch('stock_assistant.fetch_competitor_data', return_value=[])
    @patch('stock_assistant.fetch_news', return_value=[])
    @patch('stock_assistant.fetch_stock_data')
    @patch('stock_assistant.time.sleep')
    @patch('stock_assistant.StockPrerun')
    def test_main_sleep_called_when_multiple_stocks(self, mock_prerun_class, mock_sleep, mock_fetch_data, *_):
        mock_prerun = mock_prerun_class.return_value
        mock_prerun.check_setup.return_value = False
        mock_prerun.load_config.return_value = {'skip_tickers': [], 'only_tickers': []}
        mock_prerun.load_portfolio.return_value = (
            [{'symbol': 'AAPL', 'shares': 1, 'cost_basis': 1}, {'symbol': 'MSFT', 'shares': 1, 'cost_basis': 1}], [], 0.0
        )
        mock_prerun.load_company_names.return_value = {}
        mock_fetch_data.return_value = {'fundamental': {'current_price': 1}, 'technical': {'ma50': 1, 'ma200': 1}}
        with patch.object(stock_assistant, 'RESULTS_FILE', MagicMock(spec=Path)), \
             patch.object(stock_assistant, 'HTML_FILE', MagicMock(spec=Path)) as mock_html_file, \
             patch.object(sys, 'argv', ['stock_assistant.py']):
            mock_html_file.absolute.return_value = Path('index.html')
            stock_assistant.main()
        mock_sleep.assert_called()

    def test_main_entrypoint_line(self):
        with patch.object(sys, 'argv', ['stock_assistant.py', '--open']), \
             patch('webbrowser.open'), \
             patch('pathlib.Path.exists', return_value=False), \
             patch('builtins.print'):
            runpy.run_path(str(Path(__file__).resolve().parents[1] / 'stock_assistant.py'), run_name='__main__')

    @patch('stock_assistant.Path.exists', return_value=False)
    def test_fetch_competitor_data_no_config(self, mock_exists):
        res = stock_assistant.fetch_competitor_data([{'symbol': 'AAPL'}], MagicMock(), {}, {})
        self.assertEqual(res, [])

    @patch('stock_assistant.Path.exists', return_value=True)
    @patch('stock_assistant.Path.read_text', side_effect=RuntimeError('bad json'))
    def test_fetch_competitor_data_bad_config(self, mock_read, mock_exists):
        res = stock_assistant.fetch_competitor_data([{'symbol': 'AAPL'}], MagicMock(), {}, {})
        self.assertEqual(res, [])

    @patch('stock_assistant.Path.exists', return_value=True)
    @patch('stock_assistant.Path.read_text', return_value='{\"AAPL\": []}')
    def test_fetch_competitor_data_old_format_no_symbols(self, mock_read, mock_exists):
        res = stock_assistant.fetch_competitor_data([{'symbol': 'AAPL'}], MagicMock(), {}, {})
        self.assertEqual(res, [])

    def test_fetch_competitor_data_includes_candidates_txt(self):
        cache_mgr = MagicMock()
        company_names = {}
        with patch.object(stock_assistant, 'CANDIDATES_FILE', MagicMock(spec=Path)) as mock_candidates, \
             patch.object(stock_assistant, 'COMPETITORS_FILE', MagicMock(spec=Path)) as mock_comp, \
             patch('stock_assistant.fetch_holdings_data', return_value=[{'stock_info': {'symbol': 'NVDA'}}]) as mock_fetch:
            mock_comp.exists.return_value = True
            mock_comp.read_text.return_value = json.dumps({'holdings': {'AAPL': ['MSFT']}, 'competitors': {}})
            mock_candidates.exists.return_value = True
            mock_candidates.read_text.return_value = "NVDA\n# comment\nAAPL\nBRK.B\n"

            stock_assistant.fetch_competitor_data([{'symbol': 'AAPL'}], cache_mgr, company_names, {})
            competitor_stocks = mock_fetch.call_args[0][0]
            syms = [s['symbol'] for s in competitor_stocks]
            self.assertIn('MSFT', syms)
            self.assertIn('NVDA', syms)
            self.assertNotIn('AAPL', syms)

    def test_fetch_competitor_data_candidates_read_error(self):
        cache_mgr = MagicMock()
        with patch.object(stock_assistant, 'CANDIDATES_FILE', MagicMock(spec=Path)) as mock_candidates, \
             patch.object(stock_assistant, 'COMPETITORS_FILE', MagicMock(spec=Path)) as mock_comp, \
             patch('stock_assistant.fetch_holdings_data', return_value=[]):
            mock_comp.exists.return_value = True
            mock_comp.read_text.return_value = json.dumps({'holdings': {'AAPL': []}, 'competitors': {}})
            mock_candidates.exists.return_value = True
            mock_candidates.read_text.side_effect = RuntimeError("boom")
            out = stock_assistant.fetch_competitor_data([{'symbol': 'AAPL'}], cache_mgr, {}, {})
            self.assertEqual(out, [])

    @patch('stock_assistant.rebuild_dashboard')
    def test_main_html_only_branch(self, mock_rebuild):
        with patch.object(sys, 'argv', ['stock_assistant.py', '--html-only']):
            stock_assistant.main()
        mock_rebuild.assert_called_once()


class TestFetchHoldingsDataExtra(unittest.TestCase):
    @patch('stock_assistant.fetch_news', return_value=[])
    @patch('stock_assistant.fetch_stock_data')
    def test_fetch_holdings_negative_roe_scoring(self, mock_fetch_stock_data, _mock_news):
        mock_fetch_stock_data.return_value = {
            'fundamental': {'current_price': 90, 'returnOnEquity': -0.2},
            'technical': {'ma50': 100, 'ma200': 110},
        }
        out = stock_assistant.fetch_holdings_data(
            [{'symbol': 'AAPL', 'shares': 1, 'cost_basis': 100}],
            cache_mgr=MagicMock(),
            company_names={},
            config={},
            has_api_key=False,
            sleep_seconds=0,
        )
        self.assertIn('scores', out[0]['analysis_result'])



if __name__ == '__main__':

    unittest.main()





